"""Synthetic CPU transition harness, never a production parent/worker entry.

Uses an actual isolated venv interpreter and installed dist-info, tiny synthetic
wheel/ELF bytes, and the unchanged production loader verification functions.
No package installer, model, provider, authentication or evaluator is used.
"""
from contextlib import ExitStack
from pathlib import Path
import ctypes
import importlib
import json
import os
import subprocess
import sys
import time
import types
from unittest.mock import patch


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    role = sys.argv[2]
    sys.path.insert(0, data['runtime'])
    e = importlib.import_module('owned_runtime.environment_v2')
    p = importlib.import_module('owned_runtime.parent_scoring')
    from owned_runtime.release import canonical, sha
    row = {'synthetic_cpu_only': True, 'role': role, 'accepted': False,
           'prefix': sys.prefix, 'python': sys.executable, 'isolated': bool(sys.flags.isolated),
           'stage': 'installed-interpreter', 'native_load_attempted': False}
    handles = []
    with ExitStack() as stack:
        # Only synthetic wheel/hash/driver data is replaced. Prefix and metadata
        # lookup remain real, unlike the older direct-function ELF fixtures.
        stack.enter_context(patch.object(e, 'POLICY', data['policy']))
        stack.enter_context(patch.object(e, 'LOCK_SHA256', data['lock_sha256']))
        stack.enter_context(patch.object(p, 'TRUSTED_DRIVER_LIBRARY_DIRECTORIES', (data['system'],)))
        stack.enter_context(patch.object(e, '_alias_roots', return_value={name: data['system'] for name in e.ALIAS_DIRECTORIES}))
        try:
            e.need(Path(sys.prefix) == Path(data['prefix']) and sys.flags.isolated,
                   'actual isolated synthetic installed interpreter required')
            row['distribution_version'] = e.importlib.metadata.distribution(e.POLICY['distribution']).version
            if role == 'parent':
                row['stage'] = 'parent-installation-verification'
                row['preparation_environment'] = dict(os.environ)
                e.verify_cudnn_installation(data['model'], deadline=time.monotonic() + 15, diagnostic={})
                env = p.worker_environment(fixture=False)
                row['worker_environment'] = env
                if data['case'] == 'child_tampered':
                    with (Path(data['lib']) / 'libcudnn_ops.so.9').open('ab') as stream:
                        stream.write(b'tampered after parent verification')
                command = [sys.executable, '-I', '-B'] + (['-O'] if sys.flags.optimize else [])
                child = subprocess.run(command + [__file__, sys.argv[1], 'worker', sha(canonical(env))],
                    env=env, cwd=data['runtime'], capture_output=True, text=True, timeout=25, check=True)
                row['child'] = json.loads(child.stdout)
                row['accepted'] = row['child']['accepted']
                row['stage'] = 'complete'
                row['deployment_target'] = sys.argv[3:]
            else:
                row['stage'] = 'child-startup'
                if data['case'] == 'guard_bad_value':
                    os.environ['PIP_NO_INDEX'] = '0'
                if data['case'] == 'guard_extra_key':
                    os.environ['IRISX_UNREVIEWED_INJECTION'] = 'synthetic'
                request = {'config': {'fixture': False, 'model': data['model']},
                           'worker_environment_sha256': sys.argv[3]}
                p.verify_child_loader_environment(request, deadline=time.monotonic() + 15)
                row['stage'] = 'native-load'
                row['native_load_attempted'] = True
                if data['case'] == 'foreign_backend':
                    handles.append(ctypes.CDLL(str(Path(data['system']) / 'libcudnn_graph.so.9')))
                shim = ctypes.CDLL(str(Path(data['lib']) / 'libcudnn.so.9'))
                shim.cudnnGetVersion.argtypes = []
                shim.cudnnGetVersion.restype = ctypes.c_size_t
                row['api'] = int(shim.cudnnGetVersion())
                torch = types.SimpleNamespace(backends=types.SimpleNamespace(cudnn=types.SimpleNamespace(version=shim.cudnnGetVersion)))
                row['stage'] = 'mapping-admission'
                with patch.dict(sys.modules, {'torch': torch}):
                    row['observation'] = e.observe_cudnn(data['model'], deadline=time.monotonic() + 15)
                row['accepted'] = True
                row['stage'] = 'complete'
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    if role == 'parent':
        Path(data['result_path']).write_text(json.dumps(row))
    print(json.dumps(row), flush=True)
    return 1 if role == 'parent' and not row['accepted'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
