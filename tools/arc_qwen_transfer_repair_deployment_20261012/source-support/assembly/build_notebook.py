"""Build exact inactive and predispatch-only active notebooks without executing runtime."""
from __future__ import annotations
import hashlib
import json

PACKAGE = 'tools/arc_qwen_transfer_deployment_20261012'


def build(pins, files, *, active=False):
    config = f'''# Active template requires exactly one just-in-time epoch replacement before dispatch.
MANUAL_START = {active!r}
ENABLE_MODEL = {active!r}
PROFILE = "QWEN14B_TRANSFER12H"
SESSION_SECONDS = 43200
PROBE_SECONDS = 43200
EXECUTION_CUTOFF_SECONDS = 42000
OUTER_CUTOFF_SECONDS = 42180
PROVIDER_RUNTIME_SECONDS = 42300
PREDISPATCH_EPOCH = None
OUTPUT_ROOT = "/kaggle/working/irisx-qwen14b-transfer-20261012-run002"
SOURCE_PARENT = "/kaggle/working/irisx-qwen14b-transfer-20261012-source002"
INPUT_ROOT = "/kaggle/input"
CODE_ROOT = None
DATA_ROOT = None
TRAINING_ROOT = None
'''
    loader = files[PACKAGE+'/source_loader.py'].decode()
    guard = files['tools/arc_learning_agent_20261011/process_guard.py'].decode()
    preloader = files[PACKAGE+'/preloader.py'].decode()
    embedded = 'import json\nPINS = json.loads('+repr(json.dumps(pins,sort_keys=True,separators=(',',':')))+')\n'
    embedded += 'LOADER_SOURCE = '+repr(loader)+'\nGUARD_SOURCE = '+repr(guard)+'\n'
    embedded += 'EXPECTED_LOADER_SHA256 = '+repr(hashlib.sha256(loader.encode()).hexdigest())+'\n'
    embedded += 'EXPECTED_GUARD_SHA256 = '+repr(hashlib.sha256(guard.encode()).hexdigest())+'\n'
    embedded += 'PRELOADER_SOURCE = '+repr(preloader)+'\n'
    embedded += "exec(compile(PRELOADER_SOURCE, '<reviewed-transfer-preloader>', 'exec'))\n"
    run = '''RESULT = launch_reviewed_qwen_notebook(pins=PINS, config={
    'manual_start':MANUAL_START,'enable_model':ENABLE_MODEL,'profile':PROFILE,
    'session_seconds':SESSION_SECONDS,'probe_seconds':PROBE_SECONDS,'predispatch_epoch':PREDISPATCH_EPOCH,
    'execution_cutoff_seconds':EXECUTION_CUTOFF_SECONDS,'outer_cutoff_seconds':OUTER_CUTOFF_SECONDS,
    'provider_runtime_seconds':PROVIDER_RUNTIME_SECONDS,
    'output_root':OUTPUT_ROOT,'source_parent':SOURCE_PARENT,'input_root':INPUT_ROOT,
    'code_root':CODE_ROOT,'data_root':DATA_ROOT,'training_root':TRAINING_ROOT},
    loader_source=LOADER_SOURCE,guard_source=GUARD_SOURCE,
    expected_loader_sha256=EXPECTED_LOADER_SHA256,expected_guard_sha256=EXPECTED_GUARD_SHA256)
print(json.dumps({'status':RESULT['status'],'operational_success':RESULT.get('operational_success',False),
    'science_complete':RESULT.get('science_complete',False),'public_evaluation':RESULT.get('public_evaluation'),
    'public_evaluation_status':RESULT.get('public_evaluation_status')},sort_keys=True))
'''
    title = '''# Qwen3-14B true-ARC transfer experiment

Inactive save is inert. The active template also refuses to run until a finite actual predispatch epoch replaces its one None placeholder. Queue, setup, offline installation, weight hashing, calibration, all learning and generation, scoring and closure share the original 43,200-second deadline. The inner execution cutoff is 42,000 seconds, outer closure cutoff 42,180 seconds and provider runtime limit 42,300 seconds, all measured from that same epoch. No clock reset, directory reuse or implicit manual-start clock is allowed.

This generation-budget repair preserves the exact delivered 175-member baseline and prior transfer science. Generation alone uses a 180-second hard cap and normal 175-second work window, clipped to the original branch and owner deadlines. Likelihood remains 120/115 seconds; calibration and training retain their historical 120-second hard cap and branch work deadlines. A timing-only forecast refresh includes every attempted main generation and explicit non-dispatch record, with unobserved long-output tails explicitly extrapolated. Forecasts are not guarantees.

This successor preserves the exact delivered 175-member baseline. It adds true-ARC demonstration-only SFT on the preregistered 32 parents, base/64/256 checkpoints, fresh dev16 and holdout32, and fixed demo-only dev8/holdout8 TTT. C4096, full-vocabulary BF16 base and FP32 rank8 LoRA require actual hardware admission. Calibration uses the fixed behavioral cache tests; full-prefix fallback requires separate budget admission. This preparation does not claim full-model GPU validation.

Public120 is a conditional, budget-admitted full 120-task/167-test branch of one frozen method. Public targets are evaluator-only after model-owner closure and prediction sealing. The fixed goal remains micro pass@2 >=151/167. A skipped branch, operational completion or local fixture pass is not a public score.

Retain terminal-receipt.json, evidence.zip, checkpoints.zip, the entire sibling -launcher directory and exact dispatched notebook. Report TRANSFER_COMPLETE/PARTIAL/NOT_ADMITTED/FAILED and the independent public result, including all missing and invalid answers. Do not infer learning or target attainment from Kaggle COMPLETE alone.
'''
    def cell(kind, source):
        c={'cell_type':kind,'metadata':{},'source':source.splitlines(keepends=True)}
        if kind=='code': c.update(execution_count=None,outputs=[])
        return c
    notebook={'cells':[cell('markdown',title),cell('code',config),cell('code',embedded),cell('code',run)],
              'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                          'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
    for c in notebook['cells']:
        if c['cell_type']=='code': compile(''.join(c['source']),'<transfer-notebook>','exec')
    return notebook
