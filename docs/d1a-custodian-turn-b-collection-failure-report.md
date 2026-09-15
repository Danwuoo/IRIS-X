# D1a Custodian TURN-B Collection Failure Report

- Status: **TURN-B collection complete — no admissible child assets**
- Recorded: **2026-09-15T20:37:43+08:00**
- Collection authority: **explicit owner request in the coordinating task**

## Outcome

All four D1a custodian executions ended without producing a usable Authority-
policy or Semantic-verifier bundle. The two original sessions and the two
owner-authorized corrected sessions each completed a model turn, but none
created the required sealed bundle or `output/terminal-handoff.md`.

The collection outcome is:

`turn_b_collection_complete_no_admissible_assets`

This is an execution-environment and admission failure record. It is not D1a
empirical evidence, a custodian result, or evidence of model incapability.

## Preserved authority and scientific state

- Task/Oracle freeze SHA:
  `2c8fe1cc4a34484e25f3f87907ec26d78bbc9c22`.
- Task/Oracle bundle:
  `d1a-task-oracle-2026-09-15-v1`.
- Task/Oracle manifest SHA-256:
  `62fa935d7f02843cab2615dda8b9455d79c8bbcc9f6307841a9ddb95e1977564`.
- Original launch handoff commit:
  `8bafbe3c26c0b6ed9362906a8742fa005f6fa77a`.
- Corrected relaunch authorization commit:
  `93afec07d5bcb316096d447c04ebc1e2c8f1e824`.
- Corrected relaunch handoff commit:
  `a6247505807c6b1547b2e768d9f5cd995e0d9a90`.
- No Task/Oracle asset, disclosure, oracle label, task contract, or scientific
  interpretation was changed during collection.
- D1a empirical qualification remains not established. F1-B/C/D/E and novelty
  remain unchanged. D1b and Phase 7 remain unauthorized.

## Collection procedure

The collection inspected only the four external workspaces, their stdout and
stderr logs, corrected-run `last-message.txt` files, recorded PIDs, and expected
bundle/handoff paths. It then:

1. checked whether each recorded PID was still running;
2. enumerated each external workspace;
3. checked the exact expected bundle and terminal-handoff paths;
4. read terminal messages and error logs;
5. parsed JSONL event types, agent messages, command outcomes, and token usage;
6. searched the retained event streams for file-change events, patch bodies,
   policy content, verifier code, manifests, and other recoverable drafts; and
7. computed SHA-256 digests for the retained external evidence files.

All four recorded PIDs were no longer running at collection time. The
repository was clean at `a6247505807c6b1547b2e768d9f5cd995e0d9a90` before
this report was authored.

## Per-run results

| Run | Model turn | Bundle | Terminal handoff | Retained substantive result |
|---|---|---|---|---|
| Original Authority B1 | `turn.completed` | absent | absent | none; final message reports `needs_revision` |
| Original Semantic C1 | `turn.completed` | absent | absent | none; final message reports `needs_revision` |
| Corrected Authority B2 | `turn.completed` | absent | absent | none; only `last-message.txt` |
| Corrected Semantic C2 | `turn.completed` | absent | absent | no implementation; only `last-message.txt` and one preliminary observation |

The corrected output directories contained only their respective
`last-message.txt` files. No output directory contained an asset manifest,
policy file, verifier implementation, development diagnostics, independence
record, seal, bundle document, or terminal handoff.

## Problems encountered

### 1. Requested write policy did not become effective child authority

Both launch handoffs recorded `workspace-write` and approval policy `never`.
In the actual child tool environment, write attempts were rejected with:

`writing is blocked by read-only sandbox; rejected by user approval settings`

This happened in both corrected sessions as well as the original sessions. The
directly observed fact is that the child tool layer was read-only. The exact
layer that overrode or failed to apply the requested policy is **Unknown**. It
may involve the managed runtime permission profile, argument propagation, or a
host-level policy, but the retained evidence does not discriminate among these
possibilities.

### 2. Deterministic hashing was blocked by command policy

The children attempted multiple local SHA-256 methods, including PowerShell
`Get-FileHash`, `certutil`, Python, OpenSSL, and direct .NET hashing. These were
rejected before execution as `blocked by policy`. The corrected launch added
`--ignore-rules`, but the same class of rejection remained observable.

Therefore `--ignore-rules` did not establish that deterministic hashing would
be available through the actual child tool path. The exact policy source that
continued to reject these commands is **Unknown**.

### 3. The preflight was not predictive of the model-visible environment

The corrected handoff recorded a model-visible permission preflight with write
access to the Authority workspace. The later custodian executions nevertheless
encountered an enforced read-only sandbox. The preflight therefore did not
establish equivalence with the final child execution path, or the effective
permission changed between preflight and execution.

This is a concrete admission defect: launch configuration parsing, process
creation, and an immediate running state were insufficient to establish that a
child could perform its required local work.

### 4. `turn.completed` did not mean task success

All four JSONL streams ended with `turn.completed`. Each corresponding task
still failed its required artifact contract. Completion of a model turn must
not be treated as completion of the custodian role; artifact existence, schema,
digests, seal, and terminal handoff remain separate conditions.

### 5. One digest-verification claim is unsupported by retained tool evidence

Corrected Authority B2 stated that all seven disclosed inputs were SHA-256
verified. Its retained command events show the attempted hashing commands being
declined and show successful reads, but no successful local hash command. The
claim cannot be independently substantiated from the captured event stream and
must not be promoted to admission evidence.

### 6. Rejected patch payloads were not retained

Corrected stderr records that patch writes were rejected, but the patch bodies
are absent from stdout JSONL, stderr, workspace files, and output directories.
No Authority-policy draft or Semantic-verifier implementation can be recovered
from the four executions. This made the model work non-reusable even as an
unsealed draft.

### 7. The Semantic-verifier session raised an unresolved contract concern

Corrected Semantic C2 proposed exact checking for the semantic-record family
and conservative `unknown` handling for the action family because it considered
complete ledger serialization underspecified. It did not produce an
implementation, diagnostic cases, or a sealed semantic-scope record.

This is an unvalidated observation, not an admitted verifier result. A separate
contract review would be required to determine whether the public action
contract is actually ambiguous. If the frozen Task/Oracle must be revised, the
revision must receive a new bundle identity/version and restart the affected
independence chain; it must not be silently patched in place.

## Resource accounting

| Run | Input tokens | Cached input | Output tokens | Reasoning tokens |
|---|---:|---:|---:|---:|
| Original Authority B1 | 168,812 | 144,128 | 2,461 | 1,132 |
| Original Semantic C1 | 254,661 | 221,952 | 2,743 | 1,095 |
| Corrected Authority B2 | 300,956 | 262,656 | 8,660 | 3,058 |
| Corrected Semantic C2 | 404,661 | 358,400 | 14,703 | 5,319 |
| **Total** | **1,129,090** | **987,136** | **28,567** | **10,604** |

The four repository-initiated model calls yielded zero admissible child assets.
Run-attributable provider cost remains `Unknown` under the recorded ChatGPT
subscription billing mode.

## External evidence inventory

The raw evidence remains outside the repository. Paths, byte sizes, and
SHA-256 digests at collection time are recorded below.

| Evidence path | Bytes | SHA-256 |
|---|---:|---|
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\authority.stdout.jsonl` | 19,124 | `da120c9d84db3753deeabea00cf4934931f55dcb00086f2c714cb137b46924fa` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\authority.stderr.log` | 3,196 | `a5eb8e8a50421ef02112e6ccf185b4225450ebb3bf2188c133153e2ed326ac3b` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\semantic-verifier.stdout.jsonl` | 40,414 | `42b2c6046901b26a1529307c34d27e87906dcbe446eaa634f9060d7a5f8a9376` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\semantic-verifier.stderr.log` | 1,625 | `f76522fd3bcc4b74233007611a6004e2c4fb92c2916b507e0a2903caa5e3d587` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\authority-b2.stdout.jsonl` | 71,640 | `26255201c2c92440bdc52de227c70d31ed305f98b033569faf15feedffc5614b` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\authority-b2.stderr.log` | 3,624 | `3649d7b246621256d3cbac0bfaea711d2c2e63eca814737800ea6e9e284062fe` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\authority-custodian\output\last-message.txt` | 277 | `699e63d3beaefff5a17d4d01cc6bd9a4a7c233af42eb941de454ade6c5a8ea38` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\semantic-c2.stdout.jsonl` | 40,908 | `bf63c8daefdd6df1b9e485c529f8ccca2d5deec0f9907edb82bbc0ec58c6839f` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\semantic-c2.stderr.log` | 3,256 | `074de0f764aff5d70944b403caa397adab4565ad5f7f631635216db35edcce4f` |
| `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\semantic-verifier-custodian\output\last-message.txt` | 194 | `94ea4954d6a2c5ec29011127e0802b5e0b98c83854eebe7bcbf143abd9aa2374` |

## Required remediation before any further custodian launch

Do not launch another custodian under the current path merely by repeating the
same flags. A separately owner-authorized correction should first:

1. identify the effective child sandbox and command-policy source rather than
   relying on requested CLI configuration;
2. establish, through the exact final child tool path, that the child can hash
   every disclosed input and write beneath its isolated `output/` directory;
3. capture a successful create/read/hash/update test for a disposable sentinel
   file without exposing held-out information;
4. treat any model-backed admission canary as a separately authorized call and
   not as custodian evidence;
5. review the possible action-contract ambiguity before authorizing another
   Semantic-verifier authoring session; and
6. if relaunch is later authorized, use fresh workspaces and new authoring-
   session identities while preserving cumulative call/failure accounting.

No retry, relaunch, Task/Oracle revision, calibration, analysis, D1b execution,
or scientific-status update is authorized by this failure report.
