"""Closed truth-free runtime archive membership; excludes executable caches."""
from pathlib import Path
import json
import os
import re
import stat
from tools.arc_kaggle_submission import parse_json
from tools.arc_kaggle_submission import EVALUATOR_FIELDS
from tools.nvarc_native_multitask import require
from tools.nvarc_native_submission import reject_truth

ROOT_FILES={'screen.json','plan.json','material-contract.json','terminal.json','execution-ledger.jsonl',
    'caller-receipt-bindings.json','hardware.json','hardware-raw.json','source-verification.json',
    'model-verification.json','dependency-setup.log','source-verification-prepare.json','interrupted-retention.json',
    'mount-policy.json','terminal-fallback.json','dependency-readproof-receipt.json',
    'bootstrap-failure.json','outer-supervision.json','coordinator-output.log','coordinator-admitted.json'}
RUN_FILES={'caller-admissions.json','caller-admission-ledger.jsonl','worker-receipts.json','parent-verification.json',
    'hardware.json','source-verification.json','model-verification.json','export.stdout.log','export.stderr.log',
    'calibration-export.stdout.log','calibration-export.stderr.log','output-commit.json','output-projection.json',
    'native-evidence.json','submission-audit.json','submission.json','export-process.json','.output-writer.lock'}
NATIVE_FILES={'events.jsonl','checkpoint.json','result.json','hardware.json','prepared-tokens.i16le',
    'adapter-topology.json','preparation.json','prepared-rows.json','native-schedule.json','training-ledger.json',
    'baseline-inventory.json','trained-inventory.json','optimizer-state.json','cache-control.json',
    'pre-reset-inventory.json','reset-inventory.json','post-reset-control.json','prohibited-preparation.json'}
WORKER_FILES={'stdout.log','stderr.log','ready.json','launch-reservation.json','result.json','events.jsonl'}
GENERATION_FILES={'native-evidence.json','submission-audit.json','submission.json','export-process.json','manifest.json'}

# Include excluded cache entries in the walk budget. Pruning those directories
# would hide nested symlinks; reading their generated contents is unnecessary.
MAX_TREE_ENTRIES=50000
MAX_TREE_DEPTH=64
MAX_PATH_CHARACTERS=1024


def runtime_files(root):
    """Bound traversal, including caches, without following links or special files."""
    count=0
    def visit(directory):
        nonlocal count
        entries=[]
        with os.scandir(directory) as stream:
            for entry in stream:
                count+=1
                require(count<=MAX_TREE_ENTRIES,'bounded runtime archive tree entry cap exceeded')
                path=Path(entry.path);relative=path.relative_to(root).as_posix();parts=relative.split('/')
                require(len(parts)<=MAX_TREE_DEPTH and len(relative)<=MAX_PATH_CHARACTERS and
                    '\\' not in relative and ':' not in relative and
                    not any(ord(c)<32 or ord(c)==127 for c in relative),
                    'bounded safe runtime archive path required')
                mode=entry.stat(follow_symlinks=False).st_mode
                require(not stat.S_ISLNK(mode),'runtime archive cannot follow symlinks')
                require(stat.S_ISDIR(mode) or stat.S_ISREG(mode),
                    'runtime archive requires regular files and directories')
                entries.append((path,stat.S_ISDIR(mode)))
        for path,is_directory in sorted(entries):
            if is_directory:yield from visit(path)
            else:yield path
    yield from visit(root)


def partial_marker_gate(body):
    """Reject forbidden complete key tokens even in an interrupted JSON tail."""
    text=body.decode('utf-8',errors='replace')
    for match in re.finditer(r'"((?:[^"\\]|\\.)*)"\s*:',text):
        key=json.loads('"'+match.group(1)+'"')
        require(key not in EVALUATOR_FIELDS,'evaluator marker forbidden in interrupted runtime artifact')
        if key in ('contains_evaluator_truth','correctness_scored'):
            suffix=text[match.end():].lstrip()
            require(suffix.startswith('false') or 'false'.startswith(suffix),
                    'evaluated marker forbidden in interrupted runtime artifact')


def validate_members(root,*,interrupted=None,read_bytes=None):
    root=Path(root)
    read_bytes=read_bytes or (lambda path:path.read_bytes())
    require(not any(path.is_symlink() for path in (root,*root.parents)),
            'runtime archive cannot follow symlinks')
    screen_path=root/'screen.json'
    require(not screen_path.is_symlink(),'runtime archive cannot follow symlinks')
    require(screen_path.is_file() and screen_path.stat().st_size<=8*1024**2,
            'bounded closed runtime screen manifest required before archive')
    screen=parse_json(read_bytes(root/'screen.json'));static=set(screen['payload_sha256']);files=[]
    worker_ids={job['job_id'] for job in screen.get('workload_order',[])}|set(screen.get('worker_ids',[]))
    detected=[]
    for path in runtime_files(root):
        relative=path.relative_to(root).as_posix();parts=relative.split('/')
        # Observed in probe 002: Unsloth writes generated Python beneath the
        # declared worker's cwd. Exclude only that exact directory placement,
        # never arbitrary Python, misspelled caches or undeclared worker ranks.
        if 'unsloth_compiled_cache' in parts:
            require(len(parts)>=4 and parts[0]=='workers' and parts[1] in worker_ids and
                parts[2]=='unsloth_compiled_cache','unrecognized runtime archive member: '+relative)
            require(relative not in static,'generated worker cache cannot replace a static runtime payload')
            continue
        if any(part in ('__pycache__','triton-cache') for part in parts):continue
        normalized=re.sub(r'\.[0-9a-f]{32}\.tmp$','',relative)
        if normalized==relative and relative.endswith('.tmp'):normalized=relative[:-4]
        n=normalized.split('/');allowed=relative in static or normalized in ROOT_FILES
        if len(n)==3 and n[0]=='workers' and n[1] in worker_ids and n[2] in WORKER_FILES:allowed=True
        if screen.get('format')=='irisx/stage4-e10-end-to-end-v1':
            if normalized in {'training-release.json','output-commit.json','output-projection.json',
                    'submission.json','submission-audit.json','candidate-pools.json','coverage.json','task-timings.json',
                    '.output-writer.lock'}:allowed=True
            if len(n)==3 and n[0]=='.output-generations' and re.fullmatch('[0-9a-f]{32}',n[1]) and n[2] in {
                    'submission.json','submission-audit.json','candidate-pools.json','coverage.json','task-timings.json','manifest.json'}:allowed=True
            if len(n)==3 and n[0]=='workers' and n[1] in worker_ids and n[2] in NATIVE_FILES|{
                    'texts.json','expected-rows.json','training-ready.json','training-window.json',
                    'inference-events.jsonl','answer-checkpoint.json','inference-forward-diagnostics.json',
                    'trained-inference-transition.json','reset-inference-transition.json'}:allowed=True
        if screen.get('format')=='irisx/stage4-e10-paired-schedule-v1':
            paired_outputs={'interleaved-answers.json','deferred-answers.json',
                'interleaved-audit.json','deferred-audit.json','interleaved-candidate-pools.json',
                'deferred-candidate-pools.json','paired-summary.json','paired-task-timings.json'}
            if normalized in paired_outputs:allowed=True
            if normalized in {'training-release.json','output-commit.json','output-projection.json','.output-writer.lock'}:allowed=True
            if len(n)==3 and n[0]=='workers' and n[1] in worker_ids and n[2] in NATIVE_FILES|{
                'texts.json','expected-rows.json','training-ready.json','training-window.json','answer-checkpoint.json',
                'trained-inference-transition.json','reset-inference-transition.json'}:allowed=True
            if len(n)==3 and n[0]=='.output-generations' and re.fullmatch('[0-9a-f]{32}',n[1]) and n[2] in paired_outputs|{'manifest.json'}:allowed=True
            if len(n)==5 and n[0]=='workers' and n[1] in worker_ids and n[2]=='arms' and n[3] in ('interleaved','deferred') and n[4] in {
                'inference-events.jsonl','answer-checkpoint.json','inference-forward-diagnostics.json',
                'test-allocations.json','arm-receipt.json','trained-before-inventory.json','trained-after-inventory.json',
                'model-before-metadata.json','model-after-metadata.json','adapter-entry.json'}:allowed=True
        if screen.get('format')=='irisx/stage4-e11-paired-dfs-floor-v1':
            if normalized in ('diagnostic-only.json','e11-supervision-observation.json'):allowed=True
            if screen.get('resource_budget_profile')=='owner-editor-45min-v9' and normalized=='owner-editor-confirmation.json':allowed=True
            if len(n)==3 and n[0]=='workers' and n[1] in worker_ids and n[2]=='process-launch.json':allowed=True
            paired_outputs={'p02-answers.json','p01-answers.json',
                'p02-audit.json','p01-audit.json','p02-candidate-pools.json',
                'p01-candidate-pools.json','paired-summary.json','paired-task-timings.json'}
            if normalized in paired_outputs:allowed=True
            if normalized in {'training-release.json','output-commit.json','output-projection.json','.output-writer.lock'}:allowed=True
            if len(n)==3 and n[0]=='workers' and n[1] in worker_ids and n[2] in NATIVE_FILES|{
                'texts.json','expected-rows.json','training-ready.json','training-window.json','answer-checkpoint.json',
                'trained-inference-transition.json','reset-inference-transition.json'}:allowed=True
            if len(n)==3 and n[0]=='.output-generations' and re.fullmatch('[0-9a-f]{32}',n[1]) and n[2] in paired_outputs|{'manifest.json'}:allowed=True
            if len(n)==5 and n[0]=='workers' and n[1] in worker_ids and n[2]=='arms' and n[3] in ('p02','p01') and n[4] in {
                'inference-events.jsonl','answer-checkpoint.json','inference-forward-diagnostics.json',
                'test-allocations.json','arm-receipt.json','trained-before-inventory.json','trained-after-inventory.json',
                'model-before-metadata.json','model-after-metadata.json','adapter-entry.json'}:allowed=True
        if screen.get('format') not in ('irisx/stage4-e10-paired-schedule-v1','irisx/stage4-e11-paired-dfs-floor-v1') and n[0] in ('interleaved-r1','interleaved-r2','deferred-r1','deferred-r2'):
            if len(n)==2 and n[1] in RUN_FILES:allowed=True
            if len(n)==4 and n[1]=='tasks' and n[2] in screen.get('task_ids',[]) and n[3] in ('texts.json','expected-rows.json'):allowed=True
            if len(n)==5 and n[1]=='tasks' and n[2] in screen.get('task_ids',[]) and n[3]=='native' and n[4] in NATIVE_FILES:allowed=True
            if len(n)==4 and n[1]=='.output-generations' and re.fullmatch('[0-9a-f]{32}',n[2]) and n[3] in GENERATION_FILES:allowed=True
        require(allowed,'unrecognized runtime archive member: '+relative)
        if relative in static:
            import hashlib
            require(hashlib.sha256(read_bytes(path)).hexdigest()==screen['payload_sha256'][relative],
                    'static runtime archive source/input differs: '+relative)
        if relative not in static and (normalized.endswith('.json') or normalized.endswith('.jsonl')):
            body=read_bytes(path)
            if normalized.endswith('.jsonl'):
                lines=body.splitlines(keepends=True)
                for index,line in enumerate(lines):
                    if not line.strip():continue
                    try:reject_truth(parse_json(line))
                    except (json.JSONDecodeError,UnicodeDecodeError):
                        require(index==len(lines)-1 and not line.endswith(b'\n'),
                                'malformed complete/middle runtime ledger line')
                        partial_marker_gate(line)
                        detected.append({'path':relative,'kind':'uncommitted final ledger tail','qualified':False})
            else:
                try:reject_truth(parse_json(body))
                except (json.JSONDecodeError,UnicodeDecodeError):
                    generation_partial=False
                    if len(n)==4 and n[1]=='.output-generations' and re.fullmatch('[0-9a-f]{32}',n[2]):
                        marker=root/n[0]/'output-commit.json'
                        selected=parse_json(read_bytes(marker))['generation'] if marker.exists() else None
                        manifest=path.parent/'manifest.json'
                        generation_partial=selected!=n[2] and (not manifest.exists() or manifest==path)
                    if len(n)==3 and n[0]=='.output-generations' and re.fullmatch('[0-9a-f]{32}',n[1]):
                        marker=root/'output-commit.json'
                        selected=parse_json(read_bytes(marker))['generation'] if marker.exists() else None
                        manifest=path.parent/'manifest.json'
                        generation_partial=selected!=n[1] and (not manifest.exists() or manifest==path)
                    require(relative.endswith('.tmp') or generation_partial,
                            'corrupted committed artifact cannot be retained as an interrupted write')
                    partial_marker_gate(body)
                    detected.append({'path':relative,'kind':'uncommitted generation member' if generation_partial else 'uncommitted temporary JSON','qualified':False})
        files.append(path)
    index=root/'interrupted-retention.json'
    if index.exists():
        value=parse_json(read_bytes(index))
        require(set(value)=={'format','artifacts','promotion','candidate_qualification'} and
            value['format']=='irisx/unqualified-interrupted-artifacts-v1' and value['artifacts']==detected and
            value['promotion'] is value['candidate_qualification'] is False,
            'closed recomputed interrupted-artifact retention index differs')
    if interrupted is not None:interrupted.extend(detected)
    return files
