"""Finite entrypoint using the unchanged wrapper's existing official environment.

Run with ordinary Python; this execs only the existing venv interpreter and one
hash-bound local entry. No shell, arbitrary script, secret environment, grant,
credential read/copy or second process remains after exec. The parent is publisher.
"""
from pathlib import Path
import hashlib
import os
import stat
import sys

REPOSITORY=Path(__file__).absolute().parents[3]
WRAPPER=REPOSITORY.parent/'kaggle_setup/kaggle.sh'
WRAPPER_SHA256='46134808e2705d45d70bdc9aadd26a1e1863628d3d045a32a507efa56616b4bc'
# Existing runtime trust bundle, observed before this adapter was invoked.
# This pins already trusted bytes; it neither installs a CA nor expands trust.
EXISTING_CA_SHA256='ab6933a81e6f0d142e6d5f58ed465589d899a523c2752055761af11d4ee38f2b'
ENTRY_SHA256={'rl_transport.py': 'a4da4850d7a2e44af2d85d4be65e55913a746ddeb66a26238500457911261bac', 'rl_collect.py': '71603a1eb47b1b7656f2ca6a8f2b2eb6faa99469a27aef63d4f0446828ef3a78'}


def existing_requests_ca(environment):
    """Preserve Requests' existing CA selection without adding a trust source."""
    value=environment.get('REQUESTS_CA_BUNDLE')
    if value is None:return
    path=Path(value)
    if not value or not path.is_absolute() or '..' in path.parts or str(path)!=value:
        raise ValueError('existing_requests_ca_absolute_file_required')
    for item in (path,*path.parents):
        if item.is_symlink():raise ValueError('linked_existing_requests_ca')
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size>1024**2:
        raise ValueError('existing_requests_ca_regular_bounded')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=EXISTING_CA_SHA256:
        raise ValueError('existing_requests_ca_bytes_changed')
    # Requests gives this selector priority over CURL_CA_BUNDLE. No fallback,
    # alternate bundle, verification-disable switch or custom client cert enters.


def plan(argv):
    if len(argv)<2 or argv[0] not in ('publish','collect'):
        raise ValueError('usage: launch.py publish|collect ACTION [reviewed contract arguments]')
    for p in (WRAPPER,*WRAPPER.parents):
        if p.is_symlink():raise ValueError('linked_existing_wrapper')
    if hashlib.sha256(WRAPPER.read_bytes()).hexdigest()!=WRAPPER_SHA256:raise ValueError('existing_wrapper_bytes')
    entry=Path(__file__).absolute().with_name('rl_transport.py' if argv[0]=='publish' else 'rl_collect.py')
    for p in (entry,*entry.parents):
        if p.is_symlink():raise ValueError('linked_operator_source')
    if hashlib.sha256(entry.read_bytes()).hexdigest()!=ENTRY_SHA256[entry.name]:raise ValueError('operator_source_bytes')
    base=WRAPPER.parent;python=base/'venv/bin/python'
    if not python.is_file():raise ValueError('existing_venv_missing')
    # The existing venv's Python is normally a symlink to the trusted runtime.
    # Match the checked existing executable; never choose a caller-supplied one.
    environment={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TMPDIR','REQUESTS_CA_BUNDLE','SSL_CERT_FILE','SSL_CERT_DIR','HTTPS_PROXY','HTTP_PROXY','ALL_PROXY','NO_PROXY','https_proxy','http_proxy','all_proxy','no_proxy')}
    existing_requests_ca(environment)
    environment.update(HOME=str(base/'home'),KAGGLE_CONFIG_DIR=str(base/'home/.kaggle'),PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0')
    return str(python),[str(python),'-I','-B',str(entry),*argv[1:]],environment

def main():
    executable,argv,environment=plan(sys.argv[1:])
    os.execve(executable,argv,environment)

if __name__=='__main__':main()
