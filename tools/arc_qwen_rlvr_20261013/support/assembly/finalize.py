"""Pure offline JIT byte assembly. No clock, randomness, writes, imports of model code."""
from pathlib import Path
import hashlib, json, math, stat, sys, types


def read(path,maximum=64*1024**2):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size>maximum:
        raise ValueError('bounded regular finalization input required')
    return path.read_bytes()


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def finalize(candidate_root:Path,epoch:int)->dict[str,bytes]:
    if type(epoch) is not int or epoch<=0:raise ValueError('explicit positive integer original epoch required')
    root=Path(candidate_root).absolute()
    release=json.loads(read(root/'notebook-release.json',2*1024**2))
    if release.get('production_admitted') is not True or release.get('release_role')!='rlvr002':
        raise ValueError('independently admitted exact candidate required; templates do not authorize RUN')
    helper=root/'code-payload/deployment/notebook_builder.py'
    raw=read(helper)
    if sha(raw)!=release['deployment']['notebook_builder.py']['sha256']:raise ValueError('notebook builder pin differs')
    loader=read(root/'code-payload/deployment/source_loader.py')
    if sha(loader)!=release['deployment']['source_loader.py']['sha256']:raise ValueError('source loader pin differs')
    builder=types.ModuleType('rlvr_exact_notebook_builder');builder.__file__=str(helper);builder.__package__=''
    sys.modules[builder.__name__]=builder
    exec(compile(raw,str(helper),'exec',dont_inherit=True),vars(builder))
    identity=release['original_owner_request']
    if set(identity)!={'owner_id','request_id','instruction'} or not all(type(v) is str and v for v in identity.values()):
        raise ValueError('reviewed authenticated original owner identity required')
    owner={'format':'owned-rl-original-owner-request-v1','scope':'production-rl-abc','role':'rl-abc','original_epoch':epoch,**identity}
    owner_raw=encoded(owner)
    account,slug,version=release['material_pins']['data']['reference'].split('/')
    layout=release['data_mount_layout']
    if layout=='datasets-owner-slug':data=Path('/kaggle/input')/'datasets'/account/slug
    elif layout=='slug':data=Path('/kaggle/input')/slug
    else:raise ValueError('one exact independently reviewed data mount layout required')
    descriptor={'format':'owned-rl-parent-scorer-material-v1','scope':owner['scope'],'role':owner['role'],
        'owner_id':owner['owner_id'],'original_request_id':owner['request_id'],'original_request_sha256':sha(owner_raw),
        'raw_source_sha256':release['source_sha256'],'evaluator_root':str(data/'evaluator'),
        'evaluator_manifest_sha256':release['material_pins']['data']['role_manifests']['evaluator'],
        'scorer_pins_sha256':release['scorer_pins_sha256']}
    descriptor_raw=encoded(descriptor)
    operator={'format':'owned-rl-reviewed-operator-v2','scope':owner['scope'],'role':owner['role'],
        'raw_source_sha256':release['source_sha256'],'source_archive_sha256':release['source_archive_sha256'],
        'material_review_sha256':release['material_review_sha256'],'original_request_sha256':sha(owner_raw),
        'original_epoch':epoch,'original_request_id':owner['request_id'],'owner_id':owner['owner_id'],
        'parent_scorer_sha256':sha(descriptor_raw)}
    operator_raw=encoded(operator)
    notebook_raw=encoded(builder.build(release,loader.decode(),kind='active-finalized',finalized={'owner_request':owner,'operator':operator}))
    # Mirrors the unchanged parent/worker-visible boundary without hiding blobs.
    private_path=str(Path(builder.OUTPUT+'-launcher')/'parent-private-scorer.json')
    for secret in (descriptor['evaluator_root'],private_path):
        if secret.encode() in notebook_raw or secret.encode() in owner_raw or secret.encode() in operator_raw:
            raise ValueError('parent-private material path leaked to worker-visible outer document')
    return {'active-finalized.ipynb':notebook_raw,'original-request.json':owner_raw,
            'operator.json':operator_raw,'parent-private-scorer.json':descriptor_raw}
