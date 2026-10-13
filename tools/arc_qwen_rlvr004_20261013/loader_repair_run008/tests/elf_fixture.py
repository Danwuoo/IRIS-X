"""Synthetic CPU ELF inputs. These intentionally cannot authenticate real cuDNN."""
from contextlib import ExitStack
from pathlib import Path
import ctypes, hashlib, importlib, json, os, shutil, subprocess, sys, time, types, zipfile
from unittest.mock import patch


def compile_library(path, text, *, soname, libraries=()):
    source=path.with_suffix('.c');source.write_text(text)
    subprocess.run(['gcc','-shared','-fPIC','-O2','-Wl,-soname,'+soname,
                    '-o',str(path),str(source),*libraries],check=True,capture_output=True,timeout=20)
    source.unlink()


def build(root, runtime, *, needed=False):
    root=Path(root);prefix=root/'owned';site=prefix/'lib/python3.12/site-packages'
    lib=site/'nvidia/cudnn/lib';lib.mkdir(parents=True)
    system=root/'system';system.mkdir()
    for directory,value in ((lib,91002),(system,90800)):
        compile_library(directory/'libcudnn_graph.so.9',
            '#include <stddef.h>\nsize_t fixture_backend_version(void){return '+str(value)+';}\n',
            soname='libcudnn_graph.so.9')
    if needed:
        source='#include <stddef.h>\nextern size_t fixture_backend_version(void);\nsize_t cudnnGetVersion(void){return fixture_backend_version();}'
        libraries=('-Wl,--no-as-needed',str(lib/'libcudnn_graph.so.9'))
    else:
        source='''#include <stddef.h>
#include <dlfcn.h>
size_t cudnnGetVersion(void){
 void *h=dlopen("libcudnn_graph.so.9",RTLD_NOW|RTLD_LOCAL);
 if(!h)return 0;
 size_t (*f)(void)=(size_t (*)(void))dlsym(h,"fixture_backend_version");
 return f ? f() : 0;
}'''
        libraries=('-ldl',)
    compile_library(lib/'libcudnn.so.9',source,soname='libcudnn.so.9',libraries=libraries)
    (lib/'__init__.py').write_text('')
    # Third role proves verification is a complete inventory, not shim-only.
    compile_library(lib/'libcudnn_ops.so.9','int fixture_ops(void){return 42;}',soname='libcudnn_ops.so.9')
    e=importlib.import_module('owned_runtime.environment_v2')
    wheel_root=root/'wheels';(wheel_root/'wheels').mkdir(parents=True)
    wheel=wheel_root/'wheels'/e.POLICY['wheel_name']
    with zipfile.ZipFile(wheel,'x') as archive:
        for path in sorted(lib.iterdir()):archive.write(path,'nvidia/cudnn/lib/'+path.name)
        archive.writestr('nvidia/cudnn/include/cudnn_version.h','size_t CUDNNWINAPI cudnnGetVersion(void);')
    policy={**e.POLICY,'wheel_bytes':wheel.stat().st_size,'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()}
    lock=root/'lock.json';lock.write_text(json.dumps({'wheel_files':{policy['wheel_name']:{
        'name':policy['distribution'],'version':policy['distribution_version'],
        'bytes':policy['wheel_bytes'],'sha256':policy['wheel_sha256']}}}))
    result={'prefix':str(prefix),'site':str(site),'lib':str(lib),'system':str(system),'runtime':str(runtime),
            'policy':policy,'lock_sha256':hashlib.sha256(lock.read_bytes()).hexdigest(),
            'model':{'environment_lock_path':str(lock),'wheel_root_path':str(wheel_root)}}
    config=root/'fixture.json';config.write_text(json.dumps(result));return config,result


def settings(data):
    """The only fixture substitutions: tiny wheel pins, prefix, and driver root."""
    e=importlib.import_module('owned_runtime.environment_v2')
    p=importlib.import_module('owned_runtime.parent_scoring')
    distribution=types.SimpleNamespace(version=data['policy']['distribution_version'],
        locate_file=lambda member:Path(data['site'])/member)
    stack=ExitStack()
    stack.enter_context(patch.object(e,'POLICY',data['policy']))
    stack.enter_context(patch.object(e,'LOCK_SHA256',data['lock_sha256']))
    stack.enter_context(patch.object(e.sys,'prefix',data['prefix']))
    stack.enter_context(patch.object(e.importlib.metadata,'distribution',return_value=distribution))
    stack.enter_context(patch.object(p,'TRUSTED_DRIVER_LIBRARY_DIRECTORIES',(data['system'],)))
    stack.enter_context(patch.object(e,'_alias_roots',return_value={name:data['system'] for name in e.ALIAS_DIRECTORIES}))
    return stack


def child(config,case):
    data=json.loads(Path(config).read_text());sys.path.insert(0,data['runtime'])
    e=importlib.import_module('owned_runtime.environment_v2');p=importlib.import_module('owned_runtime.parent_scoring')
    observation=None;error=None;api=None;stage='child-startup';handles=[]
    with settings(data):
        try:
            expected=p.worker_environment(fixture=False)
            if case not in ('historical','late_env','system_first'):
                request={'config':{'fixture':False,'model':data['model']},
                         'worker_environment_sha256':e.file_sha(config)}
                from owned_runtime.release import canonical,sha
                request['worker_environment_sha256']=sha(canonical(expected))
                p.verify_child_loader_environment(request,deadline=time.monotonic()+15)
            stage='native-load'
            if case=='late_env':os.environ['LD_LIBRARY_PATH']=expected['LD_LIBRARY_PATH']
            if case=='preloaded_foreign':handles.append(ctypes.CDLL(str(Path(data['system'])/'libcudnn_graph.so.9')))
            shim=ctypes.CDLL(str(Path(data['lib'])/'libcudnn.so.9'))
            shim.cudnnGetVersion.argtypes=[];shim.cudnnGetVersion.restype=ctypes.c_size_t
            api=int(shim.cudnnGetVersion())
            torch=types.SimpleNamespace(backends=types.SimpleNamespace(cudnn=types.SimpleNamespace(version=shim.cudnnGetVersion)))
            stage='mapping-admission'
            with patch.dict(sys.modules,{'torch':torch}):
                observation=e.observe_cudnn(data['model'],deadline=time.monotonic()+15)
            stage='complete'
        except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)}
    print(json.dumps({'fixture_only':True,'case':case,'accepted':observation is not None,
                     'api':api,'stage':stage,'error':error,'observation':observation,
                     'native_modules_imported':sorted(name for name in sys.modules if name in ('torch','numpy','transformers'))}))


if __name__=='__main__':
    if sys.argv[2]=='parent_preloaded':
        data=json.loads(Path(sys.argv[1]).read_text())
        foreign=ctypes.CDLL(str(Path(data['system'])/'libcudnn_graph.so.9'))
        args=[sys.executable,'-I','-B']+(['-O'] if sys.flags.optimize else [])+[__file__,sys.argv[1],'repaired']
        os.execve(sys.executable,args,dict(os.environ))
    child(sys.argv[1],sys.argv[2])
