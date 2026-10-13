"""Explicit local POSIX operator paths, versions and official credential storage.

This successor does not alter HOME, import the SDK, read credential values, or
grant publication authority. The caller must supply an independently reviewed
config hash and publication manifest hash before constructing a provider.
"""
from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from types import MappingProxyType

FORMAT = 'irisx/rlvr-local-operator-config-v1'
REF = 'danielwuu/iris-x-learning-agent-20261011'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
WINDOWS_CREDENTIAL = r'C:\Users\wurre\.kaggle\credentials.json'
WSL_CREDENTIAL = '/mnt/c/Users/wurre/.kaggle/credentials.json'
WSL_POWERSHELL = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def secure_path(value):
    need(type(value) in (str, Path) or isinstance(value, Path), 'local_path_type')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == str(value), 'local_absolute_normal_path')
    need(all(not item.is_symlink() for item in (path, *path.parents)), 'local_path_symlink')
    return path


def inside(path, root):
    return path == root or root in path.parents


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def read_json(path, expected_sha=None):
    path = secure_path(path)
    need(path.is_file() and stat.S_ISREG(path.stat().st_mode) and path.stat().st_size <= 4 * 1024**2, 'local_bounded_config')
    raw = path.read_bytes()
    if expected_sha is not None:
        need(is_sha(expected_sha) and hashlib.sha256(raw).hexdigest() == expected_sha, 'local_document_hash')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'local_duplicate_json_key')
            result[key] = value
        return result
    document = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'local_nonfinite_json'))
    need(type(document) is dict, 'local_document_object')
    return document


@dataclass(frozen=True)
class LocalConfig:
    repository_root: Path
    candidate_root: Path
    scratch_root: Path
    state_root: Path
    evidence_root: Path
    gpu_stop_path: Path
    credential_path: Path
    credential_kind: str
    versions: dict
    document_sha256: str
    publication_manifest_sha256: str


def load(config_path, config_sha256, manifest_path, manifest_sha256):
    need(os.name == 'posix', 'local_posix_runtime_required')
    import pwd
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    need(Path.home() == real_home and (not os.environ.get('HOME') or Path(os.environ['HOME']) == real_home), 'local_real_home_required')
    document = read_json(config_path, config_sha256)
    fields = {'format', 'repository_root', 'candidate_root', 'scratch_root', 'state_root', 'evidence_root', 'gpu_stop_path',
              'credential', 'username', 'publication_manifest_sha256', 'versions', 'remote_predecessor'}
    need(set(document) == fields and document['format'] == FORMAT, 'local_config_schema')
    need(document['username'] == 'danielwuu' and document['publication_manifest_sha256'] == manifest_sha256, 'local_config_identity')
    manifest = read_json(manifest_path, manifest_sha256)
    paths = {key: secure_path(document[key]) for key in ('repository_root', 'candidate_root', 'scratch_root', 'state_root', 'evidence_root', 'gpu_stop_path')}
    repository = paths['repository_root']; scratch = paths['scratch_root']
    need(repository.is_dir() and (repository / '.git').exists(), 'local_repository_required')
    need(secure_path(manifest_path).parent == paths['candidate_root'] and paths['candidate_root'].is_dir(), 'local_candidate_manifest_root')
    # Existing source is tracked; operational state must be ignored or outside it.
    if inside(scratch, repository):
        need(inside(scratch, repository / '.irisx') and scratch != repository / '.irisx', 'local_ignored_scratch_required')
    need(scratch != repository and not inside(repository, scratch), 'local_scratch_repository_overlap')
    for key in ('state_root', 'evidence_root', 'gpu_stop_path'):
        need(inside(paths[key], scratch) and paths[key] != scratch, 'local_state_outside_reviewed_scratch')
    need(paths['state_root'] != paths['evidence_root'] and not inside(paths['state_root'], paths['evidence_root']) and not inside(paths['evidence_root'], paths['state_root']), 'local_state_evidence_overlap')
    credential = document['credential']
    need(type(credential) is dict and set(credential) == {'kind', 'path'}, 'local_credential_config_schema')
    credential_path = secure_path(credential['path'])
    need(credential['kind'] in ('windows-local', 'posix-local'), 'local_credential_kind')
    need(not inside(credential_path, repository) and not inside(credential_path, scratch) and not inside(credential_path, paths['candidate_root']), 'local_credential_payload_overlap')
    if credential['kind'] == 'windows-local':
        need(str(credential_path) == WSL_CREDENTIAL, 'local_windows_credential_identity')
    else:
        need(credential_path == Path.home() / '.kaggle/credentials.json', 'local_official_posix_credential_store')
    versions = document['versions']
    need(type(versions) is dict and set(versions) == {'code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'}, 'local_version_schema')
    need(all(type(value) is int and value > 0 for value in versions.values()), 'local_version_integer')
    need(versions['code'] == versions['code_predecessor'] + 1 and versions['inactive'] == versions['inactive_predecessor'] + 1 and versions['active'] == versions['inactive'] + 1, 'local_successor_versions')
    dataset = manifest['datasets']; notebooks = {row['role']: row for row in manifest['notebooks']}
    need(len(dataset) == 1 and dataset[0]['reference'] == DREF and dataset[0]['id'] == 12504696, 'local_dataset_identity')
    need(dataset[0]['expected_predecessor_version'] == versions['code_predecessor'] and dataset[0]['expected_version'] == versions['code'], 'local_manifest_code_versions')
    need(set(notebooks) == {'inactive', 'rlvr004'}, 'local_notebook_roles')
    for role, predecessor, version in (('inactive', 'inactive_predecessor', 'inactive'), ('rlvr004', 'inactive', 'active')):
        row = notebooks[role]
        need(row['existing_notebook_id'] == 138123872 and row['existing_notebook_reference'] == REF, 'local_notebook_identity')
        need(row['expected_predecessor_version'] == versions[predecessor] and row['expected_version'] == versions[version], 'local_manifest_notebook_versions')
        need(row['dataset_sources'][0] == DREF + '/' + str(versions['code']), 'local_manifest_code_pin')
    predecessor = document['remote_predecessor']
    need(type(predecessor) is dict and set(predecessor) == {'code_version', 'notebook_version', 'notebook_source_sha256', 'provider_status', 'snapshot_sha256'}, 'local_remote_predecessor_schema')
    need(predecessor['code_version'] == versions['code_predecessor'] and predecessor['notebook_version'] == versions['inactive_predecessor'], 'local_remote_predecessor_versions')
    need(is_sha(predecessor['snapshot_sha256']) and is_sha(predecessor['notebook_source_sha256']) and predecessor['notebook_source_sha256'] == notebooks['inactive']['predecessor_source_sha256'], 'local_remote_predecessor_source')
    need(predecessor['provider_status'] in ('COMPLETE', 'ERROR', 'CANCEL_ACKNOWLEDGED'), 'local_remote_predecessor_not_terminal')
    return LocalConfig(**paths, credential_path=credential_path, credential_kind=credential['kind'], versions=MappingProxyType(dict(versions)),
                       document_sha256=config_sha256, publication_manifest_sha256=manifest_sha256)


def windows_acl_check(path, runner=subprocess.run):
    """Live Windows ACL/reparse check of the sole existing local official store.

    The command contains the path only. It never opens or emits credentials.
    Explicit SID translation handles localized Windows principal names.
    """
    need(str(secure_path(path)) == WSL_CREDENTIAL, 'local_windows_credential_identity')
    executable = secure_path(WSL_POWERSHELL)
    need(executable.is_file(), 'local_windows_acl_executable_missing')
    script = r"""$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
# WSL inherits a Windows PowerShell 7 module path; load only the modules shipped
# with this exact Windows PowerShell executable, rather than an ambient module.
Import-Module ([System.IO.Path]::Combine($PSHOME, 'Modules\Microsoft.PowerShell.Management\Microsoft.PowerShell.Management.psd1')) -ErrorAction Stop
Import-Module ([System.IO.Path]::Combine($PSHOME, 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1')) -ErrorAction Stop
$target = 'C:\Users\wurre\.kaggle\credentials.json'
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$item = Get-Item -LiteralPath $target -Force
if ($item.PSIsContainer) { throw 'credential_regular_file_required' }
$cursor = $item
while ($null -ne $cursor) {
  if (($cursor.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'credential_reparse_path' }
  if ($cursor -is [System.IO.FileInfo]) { $cursor = $cursor.Directory } else { $cursor = $cursor.Parent }
}
$acl = Get-Acl -LiteralPath $target
$owner = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
$allowed = @($sid, 'S-1-5-18', 'S-1-5-32-544')
$allowSids = @()
foreach ($rule in $acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
  if ($rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow) {
    $principal = $rule.IdentityReference.Value
    if ($principal -notin $allowed) { throw 'credential_acl_unapproved_allow_sid' }
    $allowSids += $principal
  }
}
if ($owner -ne $sid -or $sid -notin $allowSids) { throw 'credential_owner_or_access' }
@{format='irisx/local-windows-credential-acl-v1';credential_path=$target;current_user_sid=$sid;owner_sid=$owner;allow_sids=@($allowSids | Sort-Object -Unique);regular_file=$true;reparse_path=$false} | ConvertTo-Json -Compress
"""
    encoded_command = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    result = runner([str(executable), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded_command],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    need(result.returncode == 0 and len(result.stdout) <= 65536, 'local_windows_credential_acl_failed')
    try:
        proof = json.loads(result.stdout.decode('utf-8-sig'))
    except (ValueError, UnicodeError):
        raise ValueError('local_windows_credential_acl_invalid') from None
    fields = {'format', 'credential_path', 'current_user_sid', 'owner_sid', 'allow_sids', 'regular_file', 'reparse_path'}
    need(type(proof) is dict and set(proof) == fields and proof['format'] == 'irisx/local-windows-credential-acl-v1', 'local_windows_credential_acl_schema')
    sid = proof['current_user_sid']
    need(type(sid) is str and re.fullmatch(r'S-1-5-21-\d+-\d+-\d+-\d+', sid) is not None, 'local_windows_current_user_sid')
    need(proof['credential_path'] == WINDOWS_CREDENTIAL and proof['owner_sid'] == sid and proof['regular_file'] is True and proof['reparse_path'] is False, 'local_windows_credential_acl_identity')
    need(type(proof['allow_sids']) is list and sid in proof['allow_sids'] and set(proof['allow_sids']) <= {sid, 'S-1-5-18', 'S-1-5-32-544'}, 'local_windows_credential_acl_allowlist')
    return proof


def credential_guard(config):
    path = secure_path(config.credential_path)
    need(path.is_file() and stat.S_ISREG(path.stat().st_mode) and path.stat().st_size <= 65536, 'local_credential_regular_bounded')
    if config.credential_kind == 'windows-local':
        return windows_acl_check(path)
    need(os.getuid() == path.stat().st_uid and stat.S_IMODE(path.stat().st_mode) == 0o600, 'local_credential_posix_owner_mode')
    return {'format': 'irisx/local-posix-credential-mode-v1', 'owner_uid': path.stat().st_uid, 'mode': '0600', 'regular_file': True}
