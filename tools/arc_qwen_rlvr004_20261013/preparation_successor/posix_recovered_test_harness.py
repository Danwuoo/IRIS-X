"""Run unchanged recovered preparation suites in a new Linux filesystem checkout.

This supplement preserves primary Windows-filesystem failures and the missing
original installer REVIEW.json. It does not fabricate that review, change test
source, access provider credentials, or copy ignored historical evidence.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).absolute().parents[3]))
from tools.arc_qwen_rlvr004_20261013.preparation_successor import prepare as p


def run(*, repository_root, checkout_root, report_root):
    repo, checkout, report = map(p.ordinary, (repository_root, checkout_root, report_root))
    p.need(os.name == 'posix' and checkout.is_absolute() and not checkout.exists(), 'fresh explicit POSIX checkout required')
    p.need(not checkout.is_relative_to(repo) and not repo.is_relative_to(checkout), 'separate supplemental checkout required')
    p.need(report.is_relative_to(repo / '.irisx') and report.is_dir(), 'existing ignored report root required')
    p.Snapshot(repo)
    checkout.mkdir(parents=True, mode=0o700)
    process = subprocess.Popen(['git', '-C', str(repo), 'archive', p.SNAPSHOT], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        total = 0
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                name = p.relative(member.name.rstrip('/'))
                target = p.ordinary(checkout / name)
                p.need(target.is_relative_to(checkout) and (member.isfile() or member.isdir()), 'safe frozen archive member')
                if member.isdir():
                    target.mkdir(mode=0o700, parents=True, exist_ok=True)
                    continue
                total += member.size
                p.need(0 <= member.size <= p.CAP and total <= 512 * 1024**2, 'bounded frozen source checkout')
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                stream = archive.extractfile(member)
                with target.open('xb') as out:
                    shutil.copyfileobj(stream, out, length=65536)
                target.chmod(0o600)
        p.need(process.wait(timeout=30) == 0, 'frozen source archive command')
    except BaseException:
        process.kill()
        process.wait(timeout=10)
        raise
    gitdir = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--absolute-git-dir'],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30).stdout.decode().strip()
    (checkout / '.git').write_text('gitdir: ' + gitdir + '\n')
    copied = {}
    for directory in ('preparation_successor', 'installer_logging_repair', 'preparation_diagnostics_repair'):
        source = repo / p.TOOL_REL / directory
        destination = checkout / p.TOOL_REL / directory
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        for path in source.rglob('*'):
            p.ordinary(path)
            info = path.lstat()
            p.need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'ordinary supplemental sources')
            if path.is_dir() or '__pycache__' in path.parts:
                continue
            raw = p.read(path)
            name = path.relative_to(source).as_posix()
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as stream:
                stream.write(raw)
            target.chmod(0o600)
            p.need(target.read_bytes() == raw, 'unchanged test/source copy')
            copied[directory + '/' + name] = p.desc(raw)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0', HF_HUB_OFFLINE='1',
        HF_DATASETS_OFFLINE='1', TRANSFORMERS_OFFLINE='1', WANDB_MODE='offline')
    runs = []
    for mode, flags in (('normal', []), ('optimized', ['-O'])):
        log = report / ('preparation-posix-supplement-' + mode + '.log')
        command = [sys.executable, *flags, '-B', '-m', 'unittest', 'discover', '-s',
            p.TOOL_REL + '/preparation_successor', '-p', 'test_*.py', '-v']
        with log.open('xb') as stream:
            result = subprocess.run(command, cwd=checkout, env=env, stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=600, check=False)
        runs.append({'mode': mode, 'exit_code': result.returncode, 'log': str(log), **p.desc(p.read(log))})
    result = {'format': 'irisx/run006-posix-recovered-tests-supplement-v1', 'checkout_root': str(checkout),
        'frozen_snapshot': p.SNAPSHOT, 'source_inventory': copied, 'runs': runs,
        'provider_calls': 0, 'model_or_GPU_calls': 0,
        'missing_original_installer_review_synthesized': False, 'primary_filesystem_failures_preserved': True}
    with (report / 'preparation-posix-supplement.json').open('xb') as stream:
        stream.write(p.encoded(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'checkout-root', 'report-root'):
        parser.add_argument('--' + name, required=True)
    result = run(**vars(parser.parse_args()))
    print(json.dumps({'runs': result['runs'], 'checkout_root': result['checkout_root']}))


if __name__ == '__main__':
    main()
