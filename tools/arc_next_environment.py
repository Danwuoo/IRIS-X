"""Explicit manual dependency preparation and complete offline wheel lock.

Disabled by default. Uses public official PyPI/PyTorch distribution sources,
never credentials or cloud infrastructure. Run in a fresh Python 3.11/3.12
Linux x86_64 notebook environment; no model/GPU operation exists here.
"""
from __future__ import annotations
import email
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import stat
import sys
import zipfile


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def write(path,value):
    path=Path(path)
    if path.exists():raise ValueError('Fresh environment evidence destination required')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


def wheel_identity(path):
    with zipfile.ZipFile(path) as z:
        metadata=[];seen=set()
        for item in z.infolist():
            parts=PurePosixPath(item.filename)
            if item.filename in seen or parts.is_absolute() or '..' in parts.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe or duplicate wheel archive member')
            seen.add(item.filename)
            if len(parts.parts)==2 and parts.parts[0].endswith('.dist-info') and parts.parts[1]=='METADATA':
                metadata.append(item)
        if len(metadata)!=1 or metadata[0].file_size>=4*1024*1024:
            raise ValueError('One bounded root-level wheel metadata identity required')
        msg=email.message_from_bytes(z.read(metadata[0]))
        if len(msg.get_all('Name',[]))!=1 or len(msg.get_all('Version',[]))!=1:
            raise ValueError('One wheel name/version required')
        name=re.sub(r'[-_.]+','-',msg['Name']).lower();version=msg['Version']
        if not re.fullmatch('[a-z0-9][a-z0-9-]*',name) or not re.fullmatch('[a-zA-Z0-9.+!_-]+',version):
            raise ValueError('Unsafe wheel identity')
        outer=PurePosixPath(metadata[0].filename).parts[0][:-len('.dist-info')].rsplit('-',1)
        if len(outer)!=2 or re.sub(r'[-_.]+','-',outer[0]).lower()!=name or outer[1]!=version:
            raise ValueError('Root dist-info directory differs from wheel metadata identity')
        fields=Path(path).name[:-4].split('-') if Path(path).name.endswith('.whl') else []
        if len(fields) not in (5,6) or re.sub(r'[-_.]+','-',fields[0]).lower()!=name or fields[1]!=version:
            raise ValueError('Wheel filename differs from metadata identity')
        return name,version


def prepare_environment(source_lock_path,destination,*,enabled=False,install=False):
    if type(enabled) is not bool or type(install) is not bool:raise ValueError('Boolean owner switches required')
    if not enabled:return {'status':'disabled','network_calls':0,'install_calls':0}
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64') or sys.version_info[:2] not in ((3,11),(3,12)):
        raise ValueError('Fresh Linux x86_64 Python 3.11/3.12 environment required')
    dest=Path(destination)
    if dest.exists():raise ValueError('A fresh dependency destination is required')
    lock=json.loads(Path(source_lock_path).read_bytes())['proposed_training_environments']['common_hf_bf16_lora']
    packages=lock['packages'];python_tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
    torchs=[w for w in packages['torch']['wheels'] if python_tag in w['filename'] and 'manylinux' in w['filename']]
    if len(torchs)!=1:raise ValueError('Exact official torch wheel for this Python is missing')
    requirements=[name+'=='+v['version'] for name,v in packages.items() if name!='torch']
    requirements.append('torch @ '+torchs[0]['url']+'#sha256='+torchs[0]['sha256'])
    dest.mkdir(parents=True);wheels=dest/'wheels';wheels.mkdir()
    request=dest/'requested.txt';request.write_text('\n'.join(requirements)+'\n')
    # Only binary packages from well-known official registries; no source build,
    # VCS dependency, remote package setup.py or unknown vendor is admitted.
    subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:',
        '--index-url','https://pypi.org/simple','--dest',str(wheels),'-r',str(request)],check=True)
    inventory={};versions={};lines=[]
    for path in sorted(wheels.glob('*.whl')):
        name,version=wheel_identity(path)
        if name in versions:raise ValueError('Multiple versions of one dependency resolved')
        versions[name]=version;hashed=sha(path)
        if name in packages:
            expected=packages[name]
            if version!=expected['version'] or not any(w['filename']==path.name and w['sha256']==hashed for w in expected['wheels']):
                raise ValueError('Top-level wheel differs from pinned official source: '+name)
        inventory[path.name]={'name':name,'version':version,'sha256':hashed,'bytes':path.stat().st_size}
        lines.append(name+'=='+version+' --hash=sha256:'+hashed)
    if not set(packages)<=set(versions):raise ValueError('Incomplete resolved dependency set')
    requirements_lock=dest/'requirements.lock';requirements_lock.write_text('\n'.join(sorted(lines))+'\n')
    receipt={'format':'irisx/arc-next-offline-wheel-lock-v1','source_lock_sha256':sha(source_lock_path),
             'python':platform.python_version(),'platform':platform.platform(),'files':inventory,
             'requirements_sha256':sha(requirements_lock),'versions':versions,
             'all_transitive_wheels_materialized':True,'gpu_runtime_verified':False}
    write(dest/'wheel-lock.json',receipt)
    if install:
        subprocess.run([sys.executable,'-m','pip','install','--no-index','--find-links',str(wheels),
                        '--require-hashes','-r',str(requirements_lock)],check=True)
        subprocess.run([sys.executable,'-m','pip','check'],check=True)
        actual={name:importlib.metadata.version(name) for name in versions}
        if actual!=versions:raise ValueError('Installed dependency versions differ from complete wheel lock')
        env={'format':'irisx/arc-next-environment-lock-v1','versions':actual,
             'wheel_lock_sha256':sha(dest/'wheel-lock.json'),'complete_transitive_lock':True,
             'python':platform.python_version(),'source':'pinned official top-level wheels + complete resolved PyPI transitive wheels',
             'gpu_runtime_verified':False}
        write(dest/'environment-lock.json',env)
    return {'status':'prepared-and-installed' if install else 'downloaded-not-installed',
            'wheel_count':len(inventory),'wheel_lock':str(dest/'wheel-lock.json'),
            'environment_lock':str(dest/'environment-lock.json') if install else None,
            'gpu_calls':0,'note':'Restart the notebook kernel before model work; compiled CUDA compatibility is still unverified.'}
