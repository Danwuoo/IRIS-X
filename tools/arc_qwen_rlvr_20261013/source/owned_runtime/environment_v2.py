"""Source-pinned cuDNN library observation when v25 did not record its integer.

All other environment values remain exact prior measurements. This does not
infer an old cuDNN observation, admit substitute wheels, or widen device pins.
Same-process mapped libraries are checked; this is trusted-source admission,
not protection against hostile same-UID loader/reflection/memory replacement.
"""
from pathlib import Path
import ctypes, hashlib, importlib.metadata, json, math, os, re, stat, sys, time, zipfile
from .release import need,file_sha

FORMAT='owned-rl-reviewed-environment-v2'
LOCK_SHA256='da56c7221914a54e87d344956ddb87d8df16a58a09dd21b1051b37598948bfd0'
POLICY={'mode':'pinned-wheel-mapped-library-current-observation-v1','prior_runtime_integer_observed':False,
    'distribution':'nvidia-cudnn-cu12','distribution_version':'9.10.2.21',
    'wheel_name':'nvidia_cudnn_cu12-9.10.2.21-py3-none-manylinux_2_27_x86_64.whl',
    'wheel_bytes':706758467,'wheel_sha256':'949452be657fa16687d0930933f032835951ef0892b37d2d53824d1a84dc97a8',
    'library_member':'nvidia/cudnn/lib/libcudnn.so.9','library_api':'size_t cudnnGetVersion(void)'}
ENVIRONMENT_KEYS={'python_version','torch_version','transformers_version','peft_version','tokenizers_version',
                  'cuda_version','cudnn_version','device_count','devices'}


def _check_time(deadline):
    need(type(deadline) in (int,float) and math.isfinite(deadline) and time.monotonic()<deadline,'original deadline during cuDNN admission')


def _regular(path):
    path=Path(path).absolute()
    need(all(not p.is_symlink() for p in (path,*path.parents)) and path.resolve()==path,'canonical no-link cuDNN path required')
    need(stat.S_ISREG(path.stat().st_mode),'regular cuDNN file required')
    return path


def _stream_hash(stream,*,deadline,maximum):
    value=hashlib.sha256();total=0
    while True:
        _check_time(deadline);block=stream.read(1024**2)
        if not block:break
        total+=len(block);need(total<=maximum,'cuDNN verification byte ceiling');value.update(block)
    return value.hexdigest(),total


def _file_hash(path,*,deadline,maximum):
    path=_regular(path);before=path.stat();need(before.st_size<=maximum,'cuDNN file bound')
    with path.open('rb') as stream:result=_stream_hash(stream,deadline=deadline,maximum=maximum)
    after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and result[1]==after.st_size,'cuDNN file changed during hash')
    return result


def _mapped_cudnn(raw,library_root):
    """Read only our own process map. A second backend outside the pin rejects."""
    root=Path(library_root).absolute();found=set()
    for line in raw.splitlines():
        fields=line.split(None,5)
        if len(fields)<6:continue
        value=fields[5]
        if not re.search(r'(?:^|/)libcudnn[^/]*\.so(?:\.|$)',value):continue
        need(value.startswith('/') and '\\' not in value and not value.endswith(' (deleted)'),'ambiguous/deleted cuDNN mapping')
        path=Path(value)
        need(path.parent==root and str(path)==value,'loaded cuDNN backend outside pinned library directory')
        found.add(path)
    need(found,'no observed cuDNN library mapping')
    return sorted(found)


def _compare_header_and_versions(header,*,torch_version,library_version):
    # cudnn_version.h publishes a size_t no-argument ABI for this API.
    compact=re.sub(r'\s+',' ',header)
    need(re.search(r'\bsize_t\s+(?:CUDNNWINAPI\s+)?cudnnGetVersion\s*\(\s*(?:void)?\s*\)',compact) is not None,
         'pinned wheel header does not declare expected cudnnGetVersion ABI')
    need(type(torch_version) is int and type(library_version) is int and torch_version>0 and torch_version==library_version,
         'torch cuDNN runtime differs from exact mapped pinned library')


def observe_cudnn(model_config,*,deadline):
    _check_time(deadline)
    lock_path=_regular(model_config['environment_lock_path'])
    need(file_sha(lock_path)==LOCK_SHA256,'unchanged composite environment lock required')
    lock=json.loads(lock_path.read_bytes());wheel_row=lock['wheel_files'][POLICY['wheel_name']]
    need(wheel_row=={'name':POLICY['distribution'],'version':POLICY['distribution_version'],
         'bytes':POLICY['wheel_bytes'],'sha256':POLICY['wheel_sha256']},'source-owned cuDNN wheel descriptor differs')
    distribution=importlib.metadata.distribution(POLICY['distribution'])
    need(distribution.version==POLICY['distribution_version'],'exact installed cuDNN distribution required')
    library=_regular(distribution.locate_file(POLICY['library_member']))
    prefix=Path(sys.prefix).resolve();need(library.is_relative_to(prefix) and 'site-packages' in library.parts,'cuDNN must come from actual owned interpreter prefix')
    wheel=_regular(Path(model_config['wheel_root_path'])/'wheels'/POLICY['wheel_name'])
    observed_wheel=_file_hash(wheel,deadline=deadline,maximum=POLICY['wheel_bytes'])
    need(observed_wheel==(POLICY['wheel_sha256'],POLICY['wheel_bytes']),'actual exact cuDNN wheel bytes required')
    rows=[]
    with zipfile.ZipFile(wheel) as archive:
        members=archive.infolist();names=[m.filename for m in members]
        need(0<len(members)<=1024 and len(set(names))==len(names),'closed bounded cuDNN wheel members')
        headers=[n for n in names if n.startswith('nvidia/cudnn/include/') and n.endswith('.h') and n.count('/')==3]
        need(0<len(headers)<=64 and sum(archive.getinfo(n).file_size for n in headers)<=4*1024**2,'bounded pinned cuDNN API headers absent')
        header='\n'.join(archive.read(n).decode() for n in headers if archive.getinfo(n).file_size<=1024**2)
        library_members=[n for n in names if n.startswith('nvidia/cudnn/lib/') and n.count('/')==3 and
                         re.fullmatch(r'libcudnn[^/]*\.so(?:\.[0-9]+)*',Path(n).name)]
        need(POLICY['library_member'] in library_members and 0<len(library_members)<=32,'complete pinned cuDNN library set required')
        present={p.name for p in library.parent.iterdir() if p.name.startswith('libcudnn') and '.so' in p.name}
        need(present=={Path(n).name for n in library_members},'installed cuDNN library inventory differs')
        # Verify the full vendor library set before an explicit ctypes load. Any
        # transitive backend observed below must belong to this exact byte set.
        for member in library_members:
            path=_regular(library.parent/Path(member).name);info=archive.getinfo(member)
            need(not info.is_dir() and not info.flag_bits&1 and stat.S_IFMT(info.external_attr>>16) in (0,stat.S_IFREG) and
                 0<info.file_size<=POLICY['wheel_bytes']*2,'regular bounded wheel library')
            with archive.open(info) as stream:expected=_stream_hash(stream,deadline=deadline,maximum=info.file_size)
            actual=_file_hash(path,deadline=deadline,maximum=info.file_size)
            need(actual==expected and actual[1]==info.file_size,'installed cuDNN library differs from pinned wheel member')
            rows.append({'member':member,'path':str(path),'bytes':actual[1],'sha256':actual[0]})
    import torch
    observed_torch=torch.backends.cudnn.version()
    loaded=ctypes.CDLL(str(library),mode=getattr(ctypes,'RTLD_LOCAL',0))
    function=loaded.cudnnGetVersion;function.argtypes=[];function.restype=ctypes.c_size_t
    observed_library=int(function())
    _compare_header_and_versions(header,torch_version=observed_torch,library_version=observed_library)
    maps=_mapped_cudnn(Path('/proc/self/maps').read_text(),library.parent)
    need(library in maps and set(maps)<={Path(row['path']) for row in rows},'mapped cuDNN backend outside verified complete wheel library set')
    for path in maps:_regular(path)
    _check_time(deadline)
    return {'format':'owned-rl-cudnn-current-library-observation-v1','prior_runtime_integer_observed':False,
        'distribution':POLICY['distribution'],'distribution_version':distribution.version,'wheel_sha256':observed_wheel[0],
        'wheel_bytes':observed_wheel[1],'torch_cudnn_version':observed_torch,'library_cudnn_version':observed_library,
        'ctypes_signature':POLICY['library_api'],'verified_libraries':rows,'mapped_library_paths':[str(p) for p in maps],
        'all_observed_cudnn_mappings_verified':True,'full_installed_vendor_library_set_verified':True,
        'source_of_version':'current-process-observation; not an inferred v25 scalar'}


def verify_environment(expected,actual,*,model_config,native_identity,deadline):
    need(type(expected) is dict and set(expected)=={'format','actual_environment','native_identity_projection','model_config','cudnn_policy'} and
         expected['format']==FORMAT and expected['cudnn_policy']==POLICY,'closed reviewed environment-v2 required')
    need(type(actual) is dict and set(actual)==ENVIRONMENT_KEYS,'complete current environment observation required')
    prior=expected['actual_environment']
    need(type(prior) is dict and set(prior)==ENVIRONMENT_KEYS-{'cudnn_version'} and
         {k:v for k,v in actual.items() if k!='cudnn_version'}==prior,'all measured v25 environment fields must match exactly')
    projection=expected['native_identity_projection'];required={'model_key','profile_id','material_addendum_sha256','pretrained_weights_loaded','probe_pretrained_admitted'}
    need(type(projection) is dict and required<=set(projection) and all(native_identity.get(k)==v for k,v in projection.items()),'reviewed native identity projection differs')
    need(expected['model_config']==model_config,'reviewed model material configuration differs')
    observation=observe_cudnn(model_config,deadline=deadline)
    need(actual['cudnn_version']==observation['torch_cudnn_version'],'recorded actual environment differs from verified current cuDNN observation')
    return observation
