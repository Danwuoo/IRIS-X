"""Offline provider-cap data and standalone finalized-archive download rendering.

No provider, credential, runtime source, model or recovery action occurs here.
"""
import hashlib
import re


def provider_cap_fields(plan):
    seconds = plan['maximum_notebook_wall_seconds']
    if type(seconds) is not int or seconds <= 0:
        raise RuntimeError('positive exact provider session seconds required')
    if any(key in plan for key in ('owner_editor_admission','owner_editor_only','kernel_execution_type')):
        if plan.get('format')=='irisx/stage4-e10-native-ttt-resource-probe-v1':
            from tools.stage_nvarc_e10_ttt_probe import validate_admission
            validate_admission(plan,required=True)
            if plan['agent_execution_authorized']:
                return {'kernel_push_argv':None,'provider_session_timeout_seconds':seconds,
                    'provider_timeout_unit':'seconds','provider_timeout_source':'official SDK SaveKernel session_timeout_seconds',
                    'provider_timeout_enforcement_observed':False,'internal_watchdog_seconds':seconds,
                    'kernel_execution_type':'SAVE_AND_RUN_ALL','agent_execution_authorized':True,
                    'transport_mode':'one official SDK SAVE_AND_RUN_ALL; stop after admission receipt',
                    'notebook_ref':plan['notebook_ref'],'notebook_numeric_id':plan['notebook_numeric_id'],
                    'expected_notebook_version':plan['expected_notebook_version'],'monitor_after_submission':False,
                    'save_request_target':{'id':plan['notebook_numeric_id'],'slug':plan['notebook_ref'],
                        'new_title':plan['notebook_ref'].split('/',1)[1],'kernel_execution_type':'SAVE_AND_RUN_ALL'}}
        else:
            from tools.stage_nvarc_e10_probe import validate_owner_editor
            validate_owner_editor(plan)
        return {'kernel_push_argv':None,'provider_session_timeout_seconds':seconds,
            'provider_timeout_unit':'seconds','provider_timeout_source':'official SDK SaveKernel session_timeout_seconds',
            'provider_timeout_enforcement_observed':False,'manual_editor_timeout_attested':False,
            'internal_watchdog_seconds':seconds,'kernel_execution_type':'QUICK_SAVE',
            'transport_mode':'official SDK QUICK_SAVE only; owner starts Editor execution',
            'agent_execution_authorized':False,'notebook_ref':plan['notebook_ref'],
            'notebook_numeric_id':plan['notebook_numeric_id'],'expected_notebook_version':plan['expected_notebook_version'],
            'save_request_target':{'id':plan['notebook_numeric_id'],'slug':plan['notebook_ref'],
                'new_title':plan['notebook_ref'].split('/',1)[1],'kernel_execution_type':'QUICK_SAVE'},
            'runtime_control_scope':'internal notebook/child watchdog only; future Editor idle GPU/session cap unverified'}
    return {'kernel_push_argv': ['kaggle', 'kernels', 'push', '-p', 'kernel', '-t', str(seconds)],
        'provider_session_timeout_seconds': seconds, 'provider_timeout_unit': 'seconds',
        'provider_timeout_source': 'official Kaggle CLI 2.2.4: session_timeout_seconds=int(timeout)',
        'provider_timeout_enforcement_observed': False,
        'internal_watchdog_seconds': seconds,
        'transport_mode': 'CLI save-and-run; distinct from historical QUICK_SAVE-only transport'}


def cli_handoff(plan):
    from tools.nvarc_native_multitask import digest
    value={'format': 'irisx/e10-offline-cli-handoff-v1', 'run_id': plan['screen_id'],
        'plan_digest': digest(plan), **provider_cap_fields(plan), 'execute_commands': False,
        'required_before_execution': ['independent exact package review',
            'current source/material and free-resource admission', 'distinct coordinator ledger identity']}
    if plan.get('agent_execution_authorized') is True and plan.get('format')=='irisx/stage4-e10-native-ttt-resource-probe-v1':
        value['required_before_execution']=['independent exact package/source/material review',
            'fresh current quota and private free 3600-second provider admission',
            'one exact RUN receipt; no duplicate save and no monitoring after submission']
    elif 'owner_editor_admission' in plan:
        value['required_before_execution']=['independent exact package and source/material review',
            'one exact same-notebook QUICK_SAVE receipt; no automatic execution or retry',
            'owner starts Editor with four distinct L4 GPUs; runtime hardware gate remains mandatory']
        value['resource_information_status']='unavailable'
        value['resource_sufficiency_verified']=False
    return value


def render_download_cell(screen):
    """Return one self-contained cell; it cannot create or recover an archive."""
    from tools.nvarc_native_multitask import canonical
    run_id = screen['screen_id']; limit = screen['maximum_archive_uncompressed_bytes']
    if (not re.fullmatch('stage4-e10-(?:probe|screen)-[a-z0-9-]+', run_id) and run_id not in (
            'stage4-e11-probe-paired-dfs-floor-20261007-001','stage4-e11-probe-paired-dfs-floor-20261007-002',
            'stage4-e11-probe-paired-dfs-floor-20261007-003')) or type(limit) is not int or not 0 < limit <= 8*1024**3:
        raise RuntimeError('bounded exact probe/screen archive identity required')
    source = '''# Download only: validates finalized archive bytes/identity, not native evidence, exit or promotion.
import hashlib,json,os,stat,struct,zipfile
from pathlib import Path
'''
    source += 'DOWNLOAD_RUN_ID='+repr(run_id)+'\n'
    source += 'DOWNLOAD_PLAN_SHA256='+repr(hashlib.sha256(canonical(screen)).hexdigest())+'\n'
    source += 'DOWNLOAD_MAX_BYTES='+str(limit)+'\n'
    source += "DOWNLOAD_PATH=Path('/kaggle/working')/(DOWNLOAD_RUN_ID+'.zip')\n"
    source += '''def _download_checked_archive():
    path=DOWNLOAD_PATH
    if path.name!=DOWNLOAD_RUN_ID+'.zip' or any(p.is_symlink() for p in path.parents):
        raise RuntimeError('final exact-run regular archive path required')
    flags=os.O_RDONLY|os.O_NONBLOCK|getattr(os,'O_NOFOLLOW',0)
    if not getattr(os,'O_NOFOLLOW',0): raise RuntimeError('no-follow archive open required')
    with os.fdopen(os.open(path,flags),'rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 22<=before.st_size<=DOWNLOAD_MAX_BYTES+64*1024**2:
            raise RuntimeError('bounded regular finalized archive required')
        # Bound central-directory parsing before ZipFile allocates its metadata.
        stream.seek(-22,2);end=struct.unpack('<4s4H2LH',stream.read(22))
        if end[0]!=b'PK\\x05\\x06' or end[1]!=0 or end[2]!=0 or end[3]!=end[4] or end[7]!=0:
            raise RuntimeError('closed single-disk uncommented archive required')
        count,size,offset=end[4:7];central_end=before.st_size-22
        locator=None
        if before.st_size>=42:
            stream.seek(-42,2);candidate=struct.unpack('<4sLQL',stream.read(20))
            if candidate[0]==b'PK\\x06\\x07': locator=candidate
        if (count==65535 or size==0xffffffff or offset==0xffffffff) and locator is None:
            raise RuntimeError('ZIP64 end locator required')
        if locator is not None:
            if locator[0]!=b'PK\\x06\\x07' or locator[1]!=0 or locator[3]!=1:
                raise RuntimeError('closed single-disk ZIP64 locator required')
            stream.seek(locator[2]);large=struct.unpack('<4sQ2H2L4Q',stream.read(56))
            if large[0]!=b'PK\\x06\\x06' or large[1]!=44 or large[4]!=0 or large[5]!=0 or large[6]!=large[7] or locator[2]+56!=before.st_size-42:
                raise RuntimeError('bounded canonical ZIP64 end record required')
            if any(old!=sentinel and old!=new for old,sentinel,new in zip((count,size,offset),(65535,0xffffffff,0xffffffff),large[7:10])):
                raise RuntimeError('classic/ZIP64 metadata differs')
            count,size,offset=large[7:10];central_end=locator[2]
        if not 0<count<=50000 or not 0<size<=16*1024**2 or offset<0 or offset+size!=central_end:
            raise RuntimeError('bounded closed archive directory required')
        stream.seek(0)
        with zipfile.ZipFile(stream,'r') as archive:
            infos=archive.infolist();names=set();total=0
            if len(infos)!=count: raise RuntimeError('exact archive member count required')
            for info in infos:
                name=info.filename;parts=name.split('/');mode=info.external_attr>>16
                if info.orig_filename!=name or not name or len(name)>1024 or '\\\\' in name or ':' in name or any(ord(c)<32 or ord(c)==127 for c in name) or any(p in ('','.','..') for p in parts) or name in names or info.is_dir() or stat.S_IFMT(mode) not in (0,stat.S_IFREG) or info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or (info.compress_type==zipfile.ZIP_STORED and info.compress_size!=info.file_size):
                    raise RuntimeError('safe unique regular archive members required')
                names.add(name);total+=info.file_size
                if info.file_size<0 or total>DOWNLOAD_MAX_BYTES: raise RuntimeError('bounded uncompressed archive required')
            if 'screen.json' not in names or archive.getinfo('screen.json').file_size>8*1024**2:
                raise RuntimeError('bounded embedded exact screen plan required')
            body=archive.read('screen.json')
            if hashlib.sha256(body).hexdigest()!=DOWNLOAD_PLAN_SHA256 or json.loads(body).get('screen_id')!=DOWNLOAD_RUN_ID:
                raise RuntimeError('embedded exact run/plan identity differs')
            # Stream every entry to EOF for closed bytes/CRC; never extract or execute it.
            for info in infos:
                received=0
                with archive.open(info,'r') as member:
                    while True:
                        block=member.read(65536)
                        if not block: break
                        received+=len(block)
                        if received>info.file_size: raise RuntimeError('archive member size differs')
                    if info.compress_type==zipfile.ZIP_DEFLATED:
                        # CRC/length alone can accept output-complete truncated DEFLATE.
                        decoder=getattr(member,'_decompressor',None)
                        if not getattr(decoder,'eof',False) or decoder.unused_data or getattr(member,'_compress_left',-1)!=0:
                            raise RuntimeError('closed compressed archive member required')
                if received!=info.file_size: raise RuntimeError('truncated archive member')
        after=os.fstat(stream.fileno());current=path.lstat()
        identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if identity(before)!=identity(after) or identity(after)!=identity(current) or not stat.S_ISREG(current.st_mode):
            raise RuntimeError('finalized archive changed during validation')
    return path
_download_path=_download_checked_archive()
print('Exact-run archive available, including failed-run diagnostics. This does not qualify native evidence, notebook exit or promotion.')
from IPython.display import FileLink,display
display(FileLink(str(_download_path)))
'''
    compile(source, 'standalone-finalized-archive-download', 'exec')
    return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [],
        'source': source.splitlines(keepends=True)}
