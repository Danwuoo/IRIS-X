"""Compiled CPU loader fixture only; cannot authenticate production or GPU work."""
from pathlib import Path
import contextlib,ctypes,hashlib,importlib.util,io,json,os,shutil,subprocess,sys,tempfile,time,types,zipfile
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'source'))
import owned_runtime
spec=importlib.util.spec_from_file_location('owned_runtime.run007_mapping_fixture',HERE/'environment_v2.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
sys.path.insert(0,str(HERE.parent/'release/terminal-consumer'))
import consumer
cspec=importlib.util.spec_from_file_location('consumer.run007_mapping_fixture',HERE/'release_checks.py')
c=importlib.util.module_from_spec(cspec);cspec.loader.exec_module(c)


def compiled(path,value):
    source=path.parent/(path.name+'.c')
    source.write_text('#include <stddef.h>\nsize_t cudnnGetVersion(void){return '+str(value)+';}\n')
    subprocess.run(['gcc','-shared','-fPIC','-O2','-Wl,-soname,'+path.name,'-o',str(path),str(source)],
        capture_output=True,check=True,timeout=20)
    source.unlink()


def main(case):
    with tempfile.TemporaryDirectory(prefix='irisx-run007-cudnn-cpu-') as temporary:
        root=Path(temporary);prefix=root/'owned';lib=prefix/'lib/python3.12/site-packages/nvidia/cudnn/lib';lib.mkdir(parents=True)
        alias=root/'fixed-driver-alias';alias.mkdir();foreign=root/'foreign';foreign.mkdir()
        for name in ('libcudnn.so.9','libcudnn_ops.so.9','libcudnn_engines_precompiled.so.9','libcudnn_engines_runtime_compiled.so.9'):
            compiled(lib/name,91002)
        wheel=root/'wheels';(wheel/'wheels').mkdir(parents=True)
        archive=wheel/'wheels'/e.POLICY['wheel_name']
        with zipfile.ZipFile(archive,'x') as z:
            for path in sorted(lib.iterdir()):z.write(path,'nvidia/cudnn/lib/'+path.name)
            z.writestr('nvidia/cudnn/include/cudnn_version.h','size_t CUDNNWINAPI cudnnGetVersion(void);')
        policy={**e.POLICY,'wheel_bytes':archive.stat().st_size,'wheel_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
        lock=root/'environment-lock.json';lock.write_text(json.dumps({'wheel_files':{policy['wheel_name']:{
            'name':policy['distribution'],'version':policy['distribution_version'],'bytes':policy['wheel_bytes'],'sha256':policy['wheel_sha256']}}}))
        distribution=types.SimpleNamespace(version=policy['distribution_version'],locate_file=lambda member:prefix/'lib/python3.12/site-packages'/member)
        aliases={name:str(alias) for name in e.ALIAS_DIRECTORIES}
        handles=[]
        if case in ('alias','versioned_alias','multi_component_alias','foreign_exact','foreign_bytes','deleted','mixed','replaced_inode','tampered_alias','unknown_member'):
            destination=foreign if case=='foreign_exact' else alias
            name='libcudnn.so.9.10.2' if case=='versioned_alias' else 'libcudnn.so.9'
            if case=='multi_component_alias':name='libcudnn_engines_runtime_compiled.so.9.10.2'
            if case=='unknown_member':name='libcudnn_unknown.so.9'
            path=destination/name
            source=lib/'libcudnn_engines_runtime_compiled.so.9' if case=='multi_component_alias' else lib/'libcudnn.so.9'
            shutil.copyfile(source,path)
            if case=='foreign_bytes':compiled(path,91001)
            handles.append(ctypes.CDLL(str(path)))
            if case=='deleted':path.unlink()
            if case=='replaced_inode':
                replacement=alias/'replacement';shutil.copyfile(path,replacement);replacement.replace(path)
            if case=='tampered_alias':
                with path.open('ab') as stream:stream.write(b'changed-after-loader')
            if case=='mixed':
                bad=alias/'libcudnn_ops.so.9';compiled(bad,91001);handles.append(ctypes.CDLL(str(bad)))
        if case=='installed_tampered':
            with (lib/'libcudnn_ops.so.9').open('ab') as stream:stream.write(b'changed-installed-library')
        torch=types.SimpleNamespace(backends=types.SimpleNamespace(cudnn=types.SimpleNamespace(version=lambda:91001 if case=='api_mismatch' else 91002)))
        stderr=io.StringIO();result=None;error=None
        with patch.object(e,'POLICY',policy),patch.object(e,'LOCK_SHA256',e.file_sha(lock)),patch.object(e.sys,'prefix',str(prefix)),\
             patch.object(e.importlib.metadata,'distribution',return_value=distribution),patch.object(e,'_alias_roots',return_value=aliases),\
             patch.dict(sys.modules,{'torch':torch}),contextlib.redirect_stderr(stderr):
            try:result=e.observe_cudnn({'environment_lock_path':str(lock),'wheel_root_path':str(wheel)},deadline=time.monotonic()+30)
            except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)}
        diagnostics=[json.loads(line) for line in stderr.getvalue().splitlines()]
        consumer_verified=False
        if result is not None:
            c._verify_cudnn_mapping_v2(result,result['verified_libraries'],result['mapped_library_paths'],{lib})
            consumer_verified=True
        print(json.dumps({'fixture_only':True,'case':case,'accepted':result is not None,'error':error,
            'diagnostics':diagnostics,'consumer_verified':consumer_verified,'observation':result},sort_keys=True))


if __name__=='__main__':main(sys.argv[1])
