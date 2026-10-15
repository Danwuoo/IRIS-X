"""Finite offline launcher for a separately reviewed native POSIX runtime.

Only pinned source is compiled, then the exact reviewed venv interpreter replaces
this process with -I -B. No credential read, SDK import, login or provider call is
performed here. --help is local argparse help, never an authentication readiness
claim. Real HOME and already inherited proxy/TLS settings are preserved.
"""
import argparse
from pathlib import Path
import hashlib
import os
import stat
import sys
import types

CONFIG_SOURCE_SHA256 = '079a76924a216fa7a0c7e45cb7844a4d89fd0fd07086bdda87fdd5d2b2fe1873'
# Parent propagates final transport/collector source pins after binding review.
ENTRY_SHA256 = {'rl_transport.py': '4b8bb950e1c2bae351e52c85646ec0d82e39d6bf97bbe1d38eb24808e224f626', 'rl_collect.py': '150999bcfd2b6e24443576b8d75ef4b5034d7d62cca4b320631b866a4907119e'}


def pinned_source(path, digest):
    path = Path(path)
    if not path.is_absolute() or any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('linked_operator_source')
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 0 <= before.st_size <= 1024**2:
        raise ValueError('bounded_operator_source_required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or identity(info) != identity(before):
            raise ValueError('operator_source_identity_changed')
        raw = stream.read(1024**2 + 1)
        after = os.fstat(stream.fileno())
        current = path.lstat()
        if not stat.S_ISREG(current.st_mode) or identity(after) != identity(before) or identity(current) != identity(before):
            raise ValueError('operator_source_identity_changed')
    if len(raw) != before.st_size or len(raw) > 1024**2 or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('operator_source_bytes')
    return raw


def config_module():
    path = Path(__file__).absolute().with_name('config.py')
    raw = pinned_source(path, CONFIG_SOURCE_SHA256)
    name = 'reviewed_portable_launch_config_' + CONFIG_SOURCE_SHA256
    module = types.ModuleType(name); module.__file__ = str(path); module.__package__ = ''
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    except BaseException:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise
    return module


def binding_arguments(argv):
    """Reject duplicate/abbreviated binding flags before forwarding exact args."""
    names = ('--local-config', '--local-config-sha')
    counts = dict.fromkeys(names, 0)
    if len(argv) > 128 or any(type(arg) is not str or len(arg) > 8192 or '\x00' in arg for arg in argv):
        raise ValueError('bounded_operator_arguments_required')
    for arg in argv:
        name = arg.split('=', 1)[0]
        if name == '--':
            raise ValueError('ambiguous_binding_arguments')
        if name in names:
            counts[name] += 1
        elif name.startswith('--') and any(full.startswith(name) for full in names):
            raise ValueError('abbreviated_binding_arguments')
    if any(count != 1 for count in counts.values()):
        raise ValueError('exactly_one_local_config_binding_required')
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('--local-config', required=True)
    parser.add_argument('--local-config-sha', required=True)
    args, _ = parser.parse_known_args(argv)
    return args


def plan(argv):
    if len(argv) < 2 or argv[0] not in ('publish', 'collect') or argv[1].startswith('-'):
        raise ValueError('usage: launch.py publish|collect ACTION [reviewed contract arguments]')
    args = binding_arguments(argv[1:])
    module = config_module()
    runtime = module.read_runtime(args.local_config, args.local_config_sha)
    entry = Path(__file__).absolute().with_name('rl_transport.py' if argv[0] == 'publish' else 'rl_collect.py')
    pinned_source(entry, ENTRY_SHA256[entry.name])
    environment = module.child_environment(runtime, os.environ)
    return str(runtime.executable), [str(runtime.executable), '-I', '-B', str(entry), *argv[1:]], environment


def parser():
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument('mode', choices=('publish', 'collect'))
    result.add_argument('arguments', nargs=argparse.REMAINDER,
                        help='ACTION plus original contract options, including --local-config and --local-config-sha')
    return result


def main():
    if sys.argv[1:] in (['-h'], ['--help'], ['publish', '--help'], ['collect', '--help']):
        parser().print_help()
        return 0
    executable, argv, environment = plan(sys.argv[1:])
    os.execve(executable, argv, environment)


if __name__ == '__main__':
    raise SystemExit(main())
