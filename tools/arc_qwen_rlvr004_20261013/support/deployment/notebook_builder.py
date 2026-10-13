"""Canonical notebooks. Both distributed templates are inert; JIT inputs are explicit."""
import hashlib, json

PROFILE='QWEN14B_RLVR12H'
OUTPUT='/kaggle/working/irisx-qwen14b-rlvr-20261012-run004'
SOURCE='/kaggle/working/irisx-qwen14b-rlvr-20261012-source004'


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()


def build(release, loader_source, *, kind='inactive', finalized=None):
    if kind not in ('inactive','active-template','active-finalized'):
        raise ValueError('unknown notebook kind')
    if (kind=='active-finalized') != (finalized is not None):
        raise ValueError('only exact JIT finalization activates a notebook')
    epoch=None if finalized is None else finalized['owner_request']['original_epoch']
    enabled=kind=='active-finalized'
    config=f'''# One fresh epoch is issued only by separately reviewed JIT finalization.
MANUAL_START = {enabled!r}
ENABLE_MODEL = {enabled!r}
PROFILE = {PROFILE!r}
SESSION_SECONDS = 43200
PROBE_SECONDS = 43200
EXECUTION_CUTOFF_SECONDS = 42000
OUTER_CUTOFF_SECONDS = 42180
PROVIDER_RUNTIME_SECONDS = 42300
PREDISPATCH_EPOCH = {epoch!r}
OUTPUT_ROOT = {OUTPUT!r}
SOURCE_PARENT = {SOURCE!r}
INPUT_ROOT = '/kaggle/input'
NOTEBOOK_KIND = {kind!r}
'''
    embedded='import json\nRELEASE = json.loads('+repr(json.dumps(release,sort_keys=True,separators=(',',':')))+')\n'
    embedded+='FINALIZED = json.loads('+repr(json.dumps(finalized,sort_keys=True,separators=(',',':')))+')\n'
    embedded+='LOADER_SOURCE = '+repr(loader_source)+'\n'
    run='''if not (MANUAL_START is True and ENABLE_MODEL is True):
    RESULT = {'status':'INACTIVE_NO_EXECUTION','model_loaded':False,'filesystem_accessed':False}
else:
    import hashlib, math, sys, types
    from pathlib import Path
    if NOTEBOOK_KIND != 'active-finalized' or FINALIZED is None:
        raise ValueError('independently reviewed JIT finalization is required')
    if type(PREDISPATCH_EPOCH) is not int or PREDISPATCH_EPOCH <= 0:
        raise ValueError('one fresh explicit integer predispatch epoch required')
    if (PROFILE,SESSION_SECONDS,PROBE_SECONDS,EXECUTION_CUTOFF_SECONDS,OUTER_CUTOFF_SECONDS,PROVIDER_RUNTIME_SECONDS) != ('QWEN14B_RLVR12H',43200,43200,42000,42180,42300):
        raise ValueError('fixed profile and single-clock offsets required')
    if PREDISPATCH_EPOCH != FINALIZED['owner_request']['original_epoch']:
        raise ValueError('notebook and original owner epoch differ')
    loader = {'__name__':'reviewed_rlvr_source_loader'}
    exec(compile(LOADER_SOURCE,'<reviewed-rlvr-source-loader>','exec'),loader)
    owner, slug, version = RELEASE['code_reference'].split('/')
    candidates = [Path(INPUT_ROOT)/slug,Path(INPUT_ROOT)/'datasets'/owner/slug]
    present = [p for p in candidates if p.is_dir()]
    if len(present) != 1:
        raise ValueError('one exact code Dataset mount required')
    ready = loader['load_release'](str(present[0]),SOURCE_PARENT,
        manifest_sha256=RELEASE['code_manifest_sha256'],archive_sha256=RELEASE['source_archive_sha256'])
    path=Path(ready['deployment_root'])/'launch_notebook.py'
    module=types.ModuleType('reviewed_rlvr_launch_notebook');module.__file__=str(path);module.__package__=''
    sys.modules[module.__name__]=module
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),vars(module))
    RESULT=module.launch(ready=ready,release=RELEASE,finalized=FINALIZED,loader_source=LOADER_SOURCE,
        output_root=OUTPUT_ROOT,input_root=INPUT_ROOT,epoch=PREDISPATCH_EPOCH)
print(json.dumps(RESULT,sort_keys=True))
'''
    prose='''# Qwen3-14B measured RLVR A/B/C experiment

This is a local preparation candidate until independent material, runtime, consumer and publisher reviews bind final bytes. Both distributed templates are inert. JIT activation is a separate approved action; no implicit clock is created in this notebook.

A retrains the fixed SFT256 anchor in this session. B uses four disjoint fixed batches of eight parents times eight samples, at most four committed updates. All 32 intended parents have explicit status, including unattempted ones. C continues SFT from A against the complete synchronized extra B wall time; mismatches remain explicit. Dev predictions select one frozen arm before the selected-arm PUBLIC branch; held32 is experiment-held-out rather than pristine project confirmation. No TTT, FP8 or four-L4 substitution.

Queue, preparation, offline installation, calibration, model work, scoring and closure use one actual original epoch. Inner42000, outer42180, provider42300 and absolute43200 seconds are not reset. Forecasts do not guarantee completion. The original scorer remains micro pass@2 >=151/167 across all167 queries, with missing or invalid answers counted wrong.

The actual source-owned reviewed_bootstrap owns model admission, the subprocess and closure. The scorer remains parent-only after live inner and outer closure. Metadata hashing or CPU fixtures do not demonstrate Qwen14B efficacy. Trusted-code isolation is not a same-UID security sandbox.

Retain the raw run directory, sibling evidence ZIP and external terminal JSON, separate checkpoint ZIP, complete sibling launcher lineage, and exact submitted/provider-readback notebooks. Compact evidence excludes only declared tensor bodies; default checkpoint retrieval verifies headers/presence only. Kaggle COMPLETE is not scientific success.
'''
    def cell(kind,source):
        result={'cell_type':kind,'metadata':{},'source':source.splitlines(keepends=True)}
        if kind=='code':result.update(execution_count=None,outputs=[])
        return result
    metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'},'rlvr_template_kind':kind}
    if finalized is not None:
        metadata['owned_rl_release']={'format':'owned-rl-outer-notebook-v1','operator_sha256':hashlib.sha256(encoded(finalized['operator'])).hexdigest()}
    notebook={'cells':[cell('markdown',prose),cell('code',config),cell('code',embedded),cell('code',run)],'metadata':metadata,'nbformat':4,'nbformat_minor':5}
    for item in notebook['cells']:
        if item['cell_type']=='code':compile(''.join(item['source']),'<rlvr-notebook>','exec')
    return notebook
