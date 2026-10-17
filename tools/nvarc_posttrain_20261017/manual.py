"""Build a save-only notebook whose one-shot clock is claimed at manual execution.

No authentication, provider calls, execution or capsule changes occur here.
The frozen source identity stays distinct from the new manual session identity.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import time

from . import package


def kernel_birth_epoch():
    """Conservatively include this Python kernel's idle time in its 12h budget."""
    fields = Path('/proc/self/stat').read_text(encoding='ascii').rpartition(') ')[2].split()
    ticks = int(fields[19])
    frequency = os.sysconf('SC_CLK_TCK')
    age = time.clock_gettime(time.CLOCK_BOOTTIME) - ticks / frequency
    now = time.time()
    if not math.isfinite(age) or not 0 <= age < 43200 - 300:
        raise ValueError('A fresh Linux kernel with remaining session budget is required')
    return now - age, now


def claim_manual_request(original, session_id, *, working_parent='/kaggle/working', runtime_parent='/kaggle/temp'):
    """Never overwrite or resume a claimed identity, including after an error."""
    if not isinstance(session_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{3,95}', session_id):
        raise ValueError('One exact portable manual session identity is required')
    if session_id == original.get('run_id'):
        raise ValueError('Manual session identity must differ from frozen source identity')
    old_start = original.get('started_epoch')
    if type(old_start) not in (int, float) or not math.isfinite(old_start) or original.get('session_deadline_epoch') != old_start + 43200:
        raise ValueError('Historical source clock must remain exact')
    parent = Path(working_parent)
    if not parent.is_dir() or parent.is_symlink() or not parent.is_absolute():
        raise ValueError('Existing absolute regular manual working directory required')
    runtime = Path(runtime_parent)
    if not runtime.is_absolute() or runtime.is_symlink():
        raise ValueError('Absolute non-symlink runtime parent required')
    start, first_execution = kernel_birth_epoch()
    request = copy.deepcopy(original)
    request.update(started_epoch=start, session_deadline_epoch=start + 43200,
        working_root=str(parent / session_id), runtime_root=str(runtime / session_id),
        manual_session_id=session_id,
        predecessor_clock={'started_epoch': old_start, 'session_deadline_epoch': original['session_deadline_epoch']})
    for path in (Path(request['working_root']), Path(request['working_root'] + '-source'), Path(request['runtime_root'])):
        if path.exists() or path.is_symlink():
            raise FileExistsError('Manual attempt output/runtime already exists; never reset or overwrite')
    receipt = {'format': 'irisx/manual-first-execution-v1', 'session_id': session_id,
        'first_execution_epoch': first_execution, 'started_epoch': start,
        'session_deadline_epoch': start + 43200, 'clock_basis': 'current Linux Python kernel process birth',
        'provider_allocation_start_verified': False, 'request': request,
        'original_request_sha256': hashlib.sha256(json.dumps(original, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
    claim = parent / (session_id + '-start.json')
    descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(receipt, stream, sort_keys=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'manual_session_id': session_id, 'started_epoch': start,
        'session_deadline_epoch': start + 43200, 'original_clock_preserved': True}), flush=True)
    return request


def build_manual_notebook(original_notebook, session_id):
    notebook = copy.deepcopy(original_notebook)
    if len(notebook.get('cells', [])) != 1:
        raise ValueError('Exactly one reviewed loader cell required')
    cell = notebook['cells'][0]
    source = ''.join(cell['source'])
    if cell.get('cell_type') != 'code' or cell.get('execution_count') is not None or cell.get('outputs'):
        raise ValueError('Only an unexecuted reviewed code cell is accepted')
    tree = ast.parse(source)
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'REQUEST']
    if len(assignments) != 1:
        raise ValueError('One literal reviewed request required')
    node = assignments[0]
    request = ast.literal_eval(node.value)
    if source != package.loader(request):
        raise ValueError('Source differs from reviewed immutable loader template')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{3,95}', session_id) or session_id == request['run_id']:
        raise ValueError('Fresh manual session identity required')
    prefix = ('import copy, hashlib, json, math, os, re, time\nfrom pathlib import Path\n'
              + inspect.getsource(kernel_birth_epoch) + '\n' + inspect.getsource(claim_manual_request) + '\n')
    lines = source.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno] = ['REQUEST = claim_manual_request(' + repr(request) + ', ' + repr(session_id) + ')\n']
    cell['source'] = prefix + ''.join(lines)
    compile(cell['source'], '<manual-nvarc-loader>', 'exec')
    notebook['metadata']['irisx_manual_session_id'] = session_id
    notebook['metadata']['irisx_execution_mode'] = 'QUICK_SAVE_ONLY_NO_AGENT_RUN'
    notebook['metadata']['irisx_manual_rerun_policy'] = 'one-shot identity; existing receipt/output blocks reset or resume'
    notebook['cells'].insert(0, {'cell_type': 'markdown', 'id': 'manual-start-instructions', 'metadata': {}, 'source':
        'Ready for manual execution only. Saving this notebook does not start a GPU.\n\n'
        'The first code execution claims a new one-shot session identity and preserves the original source clock. '
        'Its 12-hour software deadline includes the current Python kernel process age; provider allocation time is not independently known. '
        'Do not resume or rerun a consumed attempt. Existing start/output files fail closed instead of resetting its budget.\n\n'
        'The frozen 2B/4B model and source pins are unchanged. RTX PRO 6000 is the requested setting, not a verified allocation. '
        'Serial/2/4-way operation is selected from actual memory and throughput measurements. '
        'Any PUBLIC result remains inherited-exposure-qualified, not clean benchmark generalization.'})
    return notebook
