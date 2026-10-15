# Windows / WSL publication bridge (incomplete development checkpoint)

Current status, evidence and next steps live only in the
[development progress document](../../../research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md).
The [existing local handoff](../../../research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md)
remains the sole execution handoff. The frozen scientific A/B/C source is unchanged.

## Early native diagnostic

Only `native_probe.py`, `win_runtime.py`, and `win_supervisor.py` form this early
checkpoint. They test synthetic native processes and private temporary files;
they do not load authentication, import Kaggle, call a provider, or launch training.
The supervisor CLI in this checkpoint is an internal diagnostic, not a publication
entry point. Production source binding, framed IPC and operation-phase watchdogs
are still under development and are not admitted for real credentials or requests.

On the explicitly authorized native Windows executor, run the existing Python:

```powershell
& <existing-python.exe> -I -B <native-checkout>\tools\arc_qwen_rlvr004_20261013\publication_windows_bridge_20261015\native_probe.py
```

Keep stdout and stderr separate. Save the exact JSON and exit status. A result from
Linux reports failure, not skipped native acceptance. The diagnostic emits source
hashes, per-case outcomes and actual Job membership/closure observations. It uses
an outer observer Job to verify all processes stopped after killing the actual
Python supervisor, including extra venv launcher processes. Failures remain
failures and trigger owned-tree cleanup. These observations do not establish
production IPC, source admission, existing OAuth reuse, GPU or scientific efficacy.
