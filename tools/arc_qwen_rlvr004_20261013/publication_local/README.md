# Local publication successor

The owner's 2026-10-13 continuation authorizes the local publisher to repair,
publish, execute and collect code17 through a verified PUBLIC120 run. This
directory adapts the local operator only. It does not replace the frozen
`publication/`, `release/`, source archive, scorer, prior runs, resource, model,
seven other Dataset pins or evaluation safeguards.

`operator_common.py` derives from the preserved original whose SHA-256 is
`b7642b808fd7e0ab4055958aac04fce15abd7953ef8c67f89e136e211bd8ad76`.
It compiles the hash-pinned `config.py` bytes directly, avoiding bytecode caches.
Transport, collector, exact material approval and the independently pinned
consumer remain separately reviewed dependencies. This file grants no provider
authority by itself.

Run the operator in local WSL/POSIX with its real account HOME. Do not modify
HOME or copy cloud credentials. Supply the exact config and manifest hashes to
`configure(config_path, config_sha256, manifest_path, manifest_sha256)` before
constructing `Provider` or writing claims. The config schema is:

```json
{
  "format": "irisx/rlvr-local-operator-config-v1",
  "repository_root": "/mnt/c/Users/wurre/Desktop/IRIS-X",
  "candidate_root": "<absolute reviewed candidate directory>",
  "scratch_root": "<absolute ignored .irisx child or outside-repository scratch>",
  "state_root": "<scratch>/state",
  "evidence_root": "<scratch>/run-evidence",
  "gpu_stop_path": "<scratch>/SPRINT-GPU-STOP.json",
  "credential": {
    "kind": "windows-local",
    "path": "/mnt/c/Users/wurre/.kaggle/credentials.json"
  },
  "username": "danielwuu",
  "publication_manifest_sha256": "<exact publication manifest SHA-256>",
  "versions": {
    "code_predecessor": 16,
    "code": 17,
    "inactive_predecessor": 31,
    "inactive": 32,
    "active": 33
  },
  "remote_predecessor": {
    "code_version": 16,
    "notebook_version": 31,
    "notebook_source_sha256": "<exact observed notebook source SHA-256>",
    "provider_status": "ERROR",
    "snapshot_sha256": "<retained remote bracket SHA-256>"
  }
}
```

The example versions reflect the known predecessor; use only fresh remote
readbacks bound to the reviewed manifest. All successor versions must match the
manifest and code Dataset pin. A config cannot change a frozen manifest into a
different publication. State, evidence and the stop marker must reside under
the explicit scratch root. Credentials must be outside repository, candidate
and scratch. Unknown fields, symlinks, overlapping paths, nonfinite or duplicate
JSON, noninteger versions and a spoofed HOME are rejected.

Transport and collection roles contend on the same
`<scratch_root>/publisher.lock`, including distinct attempt-state directories
under that reviewed scratch. The role name appears in diagnostics only; it
cannot create an independent lock or a second publisher.

For the existing Windows official store, the operator calls the fixed local
Windows PowerShell executable to verify file/ancestor reparse attributes and a
live `Get-Acl` proof. The file owner must be the current Windows user SID; Allow
ACEs may name that SID, SYSTEM or Administrators only. No credential contents
are opened by that check. A native POSIX official store may instead use
`kind: posix-local` with the real user's `~/.kaggle/credentials.json`, owned by
the current UID with mode 0600.

The PowerShell check uses UTF-16LE `-EncodedCommand` through WSL and loads the
Management and Security modules from that executable's `$PSHOME/Modules`.
This avoids inherited PowerShell 7 module paths selecting incompatible modules
for the Windows PowerShell 5.1 executable. ACL checks remain unchanged.

The official SDK reads `KaggleCredentials.load(client=..., file_path=...)` from
that explicit local file. The credential instance delegates `save()` to the
official `save(file_path=...)` for the same destination. Normal renewal has a
durable intent keyed by account and previous expiration, one request per intent
and an accepted journal bound to its original claim. An unknown intent requires
separate reconciliation. It cannot silently resend. Client renewal preserves
Dataset/notebook mutation counters. No quota API exists in this adapter.

Use `Provider.output(name, version=<reviewed numeric notebook version>)` and
`Provider.dataset_download(name, version=<reviewed numeric Dataset version>)`.
There is no default/latest version. Kernel outputs are admitted for the observed
predecessor and the two reviewed successor notebook versions; Dataset bodies
are admitted for the predecessor and successor. Historical numeric Dataset
inventories retain their original bounded metadata-only behavior.

Offline regression verification from the repository root:

```sh
python3 -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_local/tests -v
python3 -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_local/tests -v
```

Tests use synthetic credentials, SDK requests and ACL results. They never load
the real credential contents, contact Kaggle, create a grant or query quota.
CPU success does not establish GPU execution, model admission, worker closure
or PUBLIC120 science. Exact source/version/settings readbacks, a single claimed
active dispatch, terminal retrieval and the full independent consumer are still
required.
