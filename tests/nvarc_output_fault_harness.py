"""Finite, observable CPU writer protocol. No test fixtures imported by child."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from tools.nvarc_output_lifecycle import atomic_bytes, diagnostic
from tools.nvarc_native_multitask import canonical, require
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_public_eval_parent import stop_process
from tools.nvarc_public_eval import MailboxReader

ROOT = Path(__file__).resolve().parents[1]
PHASES = ('startup', 'imports-ready', 'store-ready', 'barrier')

SCRIPT = r'''
import errno,json,os,sys,time
from pathlib import Path
root=Path(sys.argv[1]);mode=sys.argv[2];nonce=sys.argv[3]
def control(name,value):
 path=root/name;temporary=root/(name+'.tmp')
 with temporary.open('xb') as stream:
  stream.write(json.dumps(value,sort_keys=True).encode());stream.flush();os.fsync(stream.fileno())
 os.replace(temporary,path)
def phase(index,name,**details):
 control('control-'+str(index)+'.json',{'nonce':nonce,'phase':name,'writer_pid':os.getpid(),
  'parent_pid':os.getppid(),**details})
 if name!='barrier':
  end=time.monotonic()+15
  denied=0
  while time.monotonic()<end:
   path=root/('ack-'+str(index)+'.json')
   try:body=path.read_bytes()
   except FileNotFoundError:body=None
   except PermissionError as error:
    if os.name!='nt' or error.errno!=errno.EACCES:raise
    denied+=1
    if denied>=5:raise
    body=None
   if body is not None:
    value=json.loads(body)
    assert value=={'nonce':nonce,'phase':name}
    return
   time.sleep(.01)
  raise TimeoutError('parent acknowledgement absent: '+name)
if mode=='no-startup':time.sleep(5);sys.exit(17)
phase(0,'startup')
from tools import nvarc_output_lifecycle as life,nvarc_public_eval as public
phase(1,'imports-ready',torch_imported='torch' in sys.modules)
plan=json.loads((root/'fixture-plan.json').read_bytes());data=json.loads((root/'fixture-input.json').read_bytes())
store=public.ResultStore(root,plan,data,allow_fixture=True)
phase(2,'store-ready')
def barrier(stage,path):
 hit=(stage==mode or mode=='after-commit-replace' and stage=='after-replace' and path.name=='output-commit.json'
      or mode=='root-submission-replace' and stage=='after-replace' and path==root/'submission.json')
 if hit:
  phase(3,'barrier',stage=stage,path=str(path));time.sleep(20)
store.generation.observe=barrier
actual=life.write_exclusive
def partial(path,body):
 if mode=='temp-write' and Path(path).name=='submission.json':
  with Path(path).open('xb') as stream:
   stream.write(body[:max(1,len(body)//2)]);stream.flush();os.fsync(stream.fileno())
   barrier('temp-write',Path(path))
 else:actual(path,body)
life.write_exclusive=partial
store.commit(json.loads((root/'update-record.json').read_bytes()))
raise AssertionError('requested barrier absent')
'''


def wait_control(path, *, nonce, phase, process, timeout, overall_end,
                 now=time.monotonic, pause=time.sleep, reader=None):
    reader = MailboxReader() if reader is None else reader
    end = min(now()+timeout, overall_end)
    while now() < end:
        body = reader.read(path)
        if body is not None:
            value = parse_json(body)
            require(value['nonce'] == nonce and value['phase'] == phase and
                    type(value['writer_pid']) is int and value['writer_pid'] > 0 and
                    type(value['parent_pid']) is int and value['parent_pid'] > 0,
                    'writer control identity differs')
            return value
        if process.poll() is not None: raise RuntimeError('launcher exited before '+phase)
        pause(min(.02, max(0, end-now())))
    raise TimeoutError('writer phase deadline: '+phase)


class WriterHandle:
    """Observe actual writer exit, independently of the Windows venv launcher."""
    def __init__(self, pid):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.types = ctypes, wintypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.OpenProcess(0x100000 | 0x1000, False, pid)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        try: require(self.kernel.WaitForSingleObject(self.handle, 0) == 258, 'writer already exited at handshake')
        except BaseException:
            self.close(); raise

    def exit(self):
        if self.kernel.WaitForSingleObject(self.handle, 1000) != 0: return False, None
        code = self.types.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle, self.ctypes.byref(code)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return True, code.value

    def close(self):
        if not self.kernel.CloseHandle(self.handle): raise self.ctypes.WinError(self.ctypes.get_last_error())


def run_case(root, mode, *, phase_seconds=10, overall_seconds=40):
    root = Path(root); nonce = uuid.uuid4().hex; started = time.monotonic()
    command = [sys.executable, '-c', SCRIPT, str(root), mode, nonce]
    receipt = {'mode': mode, 'platform': sys.platform, 'nonce': nonce, 'command': command,
               'phase_seconds': phase_seconds, 'overall_seconds': overall_seconds,
               'phases': [], 'barrier_reached': False, 'errors': [],
               'writer_pid': None, 'writer_parent_pid': None, 'worker_exit_code': None,
               'worker_stopped_handle_verified': None, 'writer_stop_confirmed': None}
    process = subprocess.Popen(command, cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED='0',
        PYTHONUTF8='1', PYTHONPATH=str(ROOT), CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1'), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=os.name != 'nt')
    receipt['launcher_pid'] = process.pid; handle = None; receipt['mailbox_events'] = []
    reader = MailboxReader(observe=lambda kind, **details: receipt['mailbox_events'].append(
        {'event': kind, **{k: str(v) if isinstance(v, Path) else v for k, v in details.items()}}))
    try:
        for index, phase in enumerate(PHASES):
            observed = wait_control(root/('control-'+str(index)+'.json'), nonce=nonce, phase=phase,
                process=process, timeout=phase_seconds, overall_end=started+overall_seconds, reader=reader)
            require(observed['writer_pid'] == process.pid or observed['parent_pid'] == process.pid,
                    'writer is not the known launcher or its direct child')
            receipt['phases'].append({**observed, 'observed_seconds': time.monotonic()-started})
            if index == 0:
                receipt.update(writer_pid=observed['writer_pid'], writer_parent_pid=observed['parent_pid'])
                if os.name == 'nt': handle = WriterHandle(observed['writer_pid'])
            require(observed['writer_pid'] == receipt['writer_pid'], 'writer changed during protocol')
            if phase == 'barrier': receipt['barrier_reached'] = True
            else: atomic_bytes(root/('ack-'+str(index)+'.json'), canonical({'nonce': nonce, 'phase': phase}))
    except BaseException as error:
        receipt['errors'].append(diagnostic(error, 'protocol'))
    finally:
        # Only the known Popen tree is stopped. Never guess or kill a reported PID.
        receipt['cleanup_target'] = {'kind': 'known-Popen-tree', 'pid': process.pid, 'stop_attempted': True}
        try: stop_process(process)
        except BaseException as error: receipt['errors'].append(diagnostic(error, 'launcher-stop'))
        try:
            out, err = process.communicate(timeout=5)
            receipt.update(stdout=out.decode('utf-8', 'replace'), stderr=err.decode('utf-8', 'replace'))
        except BaseException as error: receipt['errors'].append(diagnostic(error, 'launcher-pipes'))
        receipt.update(launcher_returncode=process.poll(), launcher_stop_confirmed=process.poll() is not None)
        if handle is not None:
            try:
                stopped, code = handle.exit()
                receipt.update(worker_stopped_handle_verified=stopped, writer_stop_confirmed=stopped,
                               worker_exit_code=code)
            except BaseException as error: receipt['errors'].append(diagnostic(error, 'writer-exit'))
            finally:
                try: handle.close()
                except BaseException as error: receipt['errors'].append(diagnostic(error, 'writer-handle-close'))
        elif os.name != 'nt' and receipt['writer_pid'] == process.pid:
            receipt.update(writer_stop_confirmed=process.poll() is not None, worker_exit_code=process.returncode)
        for stream in (process.stdout, process.stderr):
            try: stream.close()
            except BaseException as error: receipt['errors'].append(diagnostic(error, 'pipe-close'))
        receipt['elapsed_seconds'] = time.monotonic()-started
        atomic_bytes(root/'process-receipt.json', canonical(receipt))
    return receipt
