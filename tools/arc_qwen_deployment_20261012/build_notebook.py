"""Deterministic output-free four-cell notebook; inactive is always the default."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

PACKAGE=Path(__file__).resolve().parent


def build(pins, *, active=False):
    config=f'''# Only this cell differs between inactive and active publication.
MANUAL_START = {active!r}
ENABLE_MODEL = {active!r}
PROFILE = "QWEN14B_CACHED_PILOT6H"
SESSION_SECONDS = 43200
PROBE_SECONDS = 21600
PREDISPATCH_EPOCH = None
OUTPUT_ROOT = "/kaggle/working/irisx-qwen14b-pilot-20261012-run004"
SOURCE_PARENT = "/kaggle/working/irisx-qwen14b-pilot-20261012-source004"
INPUT_ROOT = "/kaggle/input"
CODE_ROOT = None
DATA_ROOT = None
TRAINING_ROOT = None
'''
    loader=(PACKAGE/'source_loader.py').read_text();guard=(PACKAGE.parent/'arc_learning_agent_20261011/process_guard.py').read_text()
    preloader=(PACKAGE/'preloader.py').read_text()
    embedded='import json\nPINS = json.loads('+repr(json.dumps(pins,sort_keys=True,separators=(',',':')))+')\n'
    embedded+='LOADER_SOURCE = '+repr(loader)+'\nGUARD_SOURCE = '+repr(guard)+'\n'
    embedded+='EXPECTED_LOADER_SHA256 = '+repr(hashlib.sha256(loader.encode()).hexdigest())+'\n'
    embedded+='EXPECTED_GUARD_SHA256 = '+repr(hashlib.sha256(guard.encode()).hexdigest())+'\n'
    embedded+='PRELOADER_SOURCE = '+repr(preloader)+'\n'
    embedded+="exec(compile(PRELOADER_SOURCE, '<reviewed-qwen-preloader>', 'exec'))\n"
    run='''RESULT = launch_reviewed_qwen_notebook(pins=PINS, config={
    'manual_start':MANUAL_START,'enable_model':ENABLE_MODEL,'profile':PROFILE,
    'session_seconds':SESSION_SECONDS,'probe_seconds':PROBE_SECONDS,'predispatch_epoch':PREDISPATCH_EPOCH,
    'output_root':OUTPUT_ROOT,'source_parent':SOURCE_PARENT,'input_root':INPUT_ROOT,
    'code_root':CODE_ROOT,'data_root':DATA_ROOT,'training_root':TRAINING_ROOT},
    loader_source=LOADER_SOURCE,guard_source=GUARD_SOURCE,
    expected_loader_sha256=EXPECTED_LOADER_SHA256,expected_guard_sha256=EXPECTED_GUARD_SHA256)
print(json.dumps({'status':RESULT['status'],'operational_success':RESULT.get('operational_success',False),'science_complete':RESULT.get('science_complete',False),'public_score':None,'public_solving_admitted':False},sort_keys=True))
'''
    def cell(kind,source):
        c={'cell_type':kind,'metadata':{},'source':source.splitlines(keepends=True)}
        if kind=='code':c.update(execution_count=None,outputs=[])
        return c
    title='''# Qwen3-14B BF16 paired cached pilot

One train/development-only paired 13-case pilot on the existing Kaggle G4 setting. Version15 completed diagnostic preflight with closed process trees and no learning; its complete evidence remains preserved.
The predeclared pilot-cached-13 is selected only if the unchanged cache capability checks and measured cost forecast pass. Otherwise pilot-full-prefix-13 may be selected if feasible, or diagnostics-only. Full-cache-16 is reference-only and cannot be selected. Both pilots retain the same 13 cases, 64/128 output caps, checkpoints8/16 and equal nontransferable branch budgets. Diagnostics-only is neither operational nor scientific success.
This successor explicitly supersedes only the historical material contract probe_bounds.maximum_probe_seconds from10800 to21600. The global43200 bound, all model/precision/rank/context rules and correctness gates remain unchanged. BF16 base, FP32 rank8/alpha16 LoRA and context2048; no public scoring, FP8 or four-L4 execution claim.
All preparation, hashing, offline CPython3.12.15 installation, loading, preflight, paired training, export and closure share one immutable predispatch epoch. Effective cap21600s; provider backup21300s. Child work ends by21000s, owner stop21060s, outer work cutoff21240s, leaving bounded closure/export margins. Provider teardown or billing is not verified by process closure.
The saved default is inactive. Only the reviewed active copy and one just-in-time epoch patch may start it.
'''
    notebook={'cells':[cell('markdown',title),cell('code',config),cell('code',embedded),cell('code',run)],
        'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                    'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
    for c in notebook['cells']:
        if c['cell_type']=='code':compile(''.join(c['source']),'<qwen-notebook>','exec')
    return notebook
