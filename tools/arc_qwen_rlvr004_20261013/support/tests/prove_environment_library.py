"""Isolated actual ctypes/ELF mechanics fixture. No torch/model/GPU admission."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,time,types,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]/'portfolio63-rl-batched-20261012'
sys.path.insert(0,str(ROOT))
from owned_runtime import environment_v2 as e
sha=lambda raw:hashlib.sha256(raw).hexdigest()
with tempfile.TemporaryDirectory(prefix='rlvr-cudnn-fixture-') as tmp:
    root=Path(tmp);member='nvidia/cudnn/lib/libcudnn.so.9';site=root/'lib/python3.12/site-packages'
    lib=site/member;lib.parent.mkdir(parents=True)
    code=root/'fixture.c';code.write_text('#include <stddef.h>\nsize_t cudnnGetVersion(void) { return 91002; }\n')
    subprocess.run(['cc','-shared','-fPIC','-o',str(lib),str(code)],check=True,timeout=20,capture_output=True)
    wheelroot=root/'mount';(wheelroot/'wheels').mkdir(parents=True);wheel=wheelroot/'wheels'/e.POLICY['wheel_name']
    with zipfile.ZipFile(wheel,'w',compression=zipfile.ZIP_STORED) as z:
        z.writestr(member,lib.read_bytes());z.writestr('nvidia/cudnn/include/cudnn_graph.h','size_t CUDNNWINAPI cudnnGetVersion(void);')
    policy={**e.POLICY,'wheel_bytes':wheel.stat().st_size,'wheel_sha256':sha(wheel.read_bytes())}
    lock=root/'lock.json';lock.write_text(json.dumps({'wheel_files':{policy['wheel_name']:{'name':policy['distribution'],'version':policy['distribution_version'],'bytes':policy['wheel_bytes'],'sha256':policy['wheel_sha256']}}}))
    dist=types.SimpleNamespace(version=policy['distribution_version'],locate_file=lambda n:site/n)
    torch=types.SimpleNamespace(backends=types.SimpleNamespace(cudnn=types.SimpleNamespace(version=lambda:91002)))
    with patch.object(e,'POLICY',policy),patch.object(e,'LOCK_SHA256',sha(lock.read_bytes())),patch.object(sys,'prefix',str(root)),patch.object(e.importlib.metadata,'distribution',return_value=dist),patch.dict(sys.modules,{'torch':torch}):
        result=e.observe_cudnn({'environment_lock_path':str(lock),'wheel_root_path':str(wheelroot)},deadline=time.monotonic()+20)
    print(json.dumps({'format':'rlvr-synthetic-ctypes-fixture-v1','status':'PASS','fixture':True,'real_cudnn_wheel_checked':False,
        'real_torch_loaded':False,'model_or_GPU_loaded':False,'actual_ELF_ctypes_call':True,'actual_self_process_maps_checked':True,
        'observed_version':result['library_cudnn_version'],'verified_library_count':len(result['verified_libraries']),
        'mapped_library_count':len(result['mapped_library_paths']),'source_sha256':sha((ROOT/'owned_runtime/environment_v2.py').read_bytes())},sort_keys=True))
