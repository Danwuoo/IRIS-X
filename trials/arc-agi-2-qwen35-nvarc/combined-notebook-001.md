# Combined M2/M3 local notebook draft

Date: 2026-09-26. Status: **local implementation verified; GPU acceptance pending**.
The [owner's development plan](../../docs/plan/2026-09-26-nvarc-combined-two-gpu-notebook.md)
authorizes local work only. This draft is distinct from consumed/submitted
M2/M3 identities. Decision 0034's version-1 runtime state remains unqueried;
no monitoring, retrieval, upload, scoring or real 4B execution occurred.

## Identity and boundaries

The parent is `nvarc-m2-m3-combined-001`; children are
`nvarc-m2-m3-combined-001-m2` and `nvarc-m2-m3-combined-001-m3`. The
[complete plan](configs/m2-m3-combined-draft-001.json) has `approved: false`,
no owner decision, an unpushable `DRAFT-DO-NOT-PUSH/` ID and zero external
allowances. Its digest is
`sha256:2052311757ab3922473e0476801dde4df551e0a037795b64025fa5f17c54e0ef`.
The notebook guard and installed parent/worker entry points reject live
execution before dependency mutation or model work. There is no current live
activation path. Future owner direction requires a separately reviewed exact
package-binding/activation change; edited approval fields or Decisions
0033/0034 cannot activate this draft.

M2 retains export
`sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6`,
the original training identity and exact source/material/input digests.
Proposed work remains zero SFT, one demonstration-only LoRA step, at most four
generation calls, 64 new tokens and 128 DFS expansions per call. M3 retains
full-vocabulary pinned Qwen3.5-4B, the original public training parents and
direct-response prompts: four dependent calls, thinking disabled, 28,160
reserved tokens and stage input/output limits 4,096/512, 4,096/1,024,
4,096/3,072 and 8,192/3,072. No retry, restart or training on teacher output
is implemented. Missing candidates remain explicit; zero ranked candidates
can represent completed engineering work and establish no quality claim.

## Implementation and limits

The new staging/preflight tools produce a deterministic 15-member review
inventory containing an inspectable plan, compiled notebook, actual runtime
wheel, source bundle, exact inputs and material references. The roughly 8 GB
export is verified at its existing retained location without another copy or
Dataset. Full M3 weights remain a digest-bound existing Dataset reference;
cached tokenizer files are independently hashed. Future runtime model mounts
must verify the full weights. Rehashed extra files, changed manifests,
materials, budgets, historical identities and stale approvals fail preflight.

The prepared notebook body stays behind the inert guard. It installs the
union of pinned offline dependencies once, including PEFT, removes optional
incompatible `torchao`, and bounds commands against the 300-second setup
ceiling with a POSIX setup alarm. Shared prerequisites stop both workers;
M2 source/export and M3 full-model/tokenizer checks remain branch-specific.
Dataset resolution accepts only exact owner-qualified or explicit legacy
mounts and rejects missing/ambiguous shared mounts.

Hardware helpers inventory the allocation and select two distinct
BF16-capable L4s meeting the existing byte/MiB memory checks. A four-device
inventory can select only two active UUIDs. Each subprocess receives its UUID
in `CUDA_VISIBLE_DEVICES` before Torch import and checks one logical `cuda:0`
against the parent record. Historical standalone four-device gates and
submitted templates are unchanged. Provider resource selection is unresolved;
this draft does not assert that Kaggle offers a two-L4 allocation.

The supervisor staggers the second load until the first worker is ready,
fails or exhausts a bounded readiness wait. Work overlaps within one
monotonic 1,800-second notebook deadline, including setup and a 30-second
terminal reserve. Cleanup shares the remaining terminal deadline across both
workers. POSIX process groups and Windows kill-on-close jobs clean descendants
after primary-process exit. Separate pipe drains retain the first 8 MiB per
stdout/stderr stream and discard excess. Cleanup/diagnostic errors are
retained while both workers are reaped and an atomic aggregate is attempted
whenever its output path is writable.

Workers have separate directories, logs, results and accounting. M2 persists
each generation/verification reservation before the backend call and marks
completed returns; interrupted totals stay unknown. M3 retains dependent
stage ledgers, responses and failure causes. The aggregate distinguishes
complete, partial, failed and timed-out work, retains return codes, phases,
devices, plan/material bindings and artifact digests, and reconciles complete
counters with independent semantic checks. A zero return code alone cannot
establish completion. M2 verifies ancestry and finite completed TTT; M3
verifies all four dependent accepted stages and actual token bounds.

GPU isolation leaves host RAM, disk capacity, storage bandwidth and the
notebook shared. Existing source measurements retain peak process RSS and
CUDA memory where available. Staggered loading proves no 4B resource fit.
Torch's UUID representation, two-L4 BF16/memory fit, shared-resource pressure
and the prepared setup on Kaggle remain GPU acceptance checks.

## Offline reproduction

From the repository root, choose a new output directory for each staging run:

```powershell
python tools/stage_nvarc_combined.py --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-review-final-002
python tools/preflight_nvarc_combined.py .irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-review-final-002
$env:PYTHONPATH='src'
python -m unittest tests.test_nvarc_combined tests.test_nvarc_continuation -v
.irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py
python tools/verify_nvarc_deployment.py --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-linux-deployment-final
python tools/repository_check.py --all
```

Strict checks fail explicitly if cached source/export/tokenizer or ML
prerequisites are absent; no replacements are acquired. Default repository
tests remain offline and do not require the large caches.

| Check | Result | Retained local evidence |
| --- | --- | --- |
| CPU process/hardware/guard and teacher diagnostics | 22 final tests pass, including complete-worker reservation retention | `.irisx/nvarc-combined-focused-final-002.txt` |
| Existing full strict ML profile | 32 tests pass | `.irisx/nvarc-combined-ml-profile-001.txt` |
| Final affected installed-wheel/package checks | 5 tests pass | `.irisx/nvarc-combined-affected-strict-final-002.txt` |
| Final cached WSL deployment | Pass: checkout hidden, isolated network namespace, combined CPU probe complete | `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-linux-deployment-final/deployment-report.json` |
| Final inert package/preflight | Pass: deterministic rebuild, 15 closed members, guard verified, export/tokenizer verified by reference | `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-review-final-002/`; `.irisx/nvarc-combined-preflight-final-002.txt` |
| Repository governance/layout/tests | Pass: 236 tests, four existing optional skips | `.irisx/nvarc-combined-repository-final-002.txt` |

Final review package SHA-256 bindings:

| Artifact | SHA-256 |
| --- | --- |
| `stage-summary.json` | `0a6245ba1de951f616501120edcaa0e2ed0a4e28c052dbc7897e589bf3700c56` |
| `kernel/kaggle-notebook.ipynb` | `104bae9f63f0632b51b97649cbd40c91e02bcdf27f0eae5aa8a340ed31753ba0` |
| `kernel/kernel-metadata.json` | `ee8da49783869b4b9e422fb56b36cea9191acbf02a13ec9a813dc18758e1f528` |
| `wheel/irisx-0.2.0-py3-none-any.whl` | `bb938bb7b06d6ccab9a901d99f9aea1655e4c9dbe5ae69bb4adb16683ddff803` |
| `plan.json` bytes | `7014795d4ea7f098a8f9680b32843039a2c76b946fd920789491743201ebcc22` |

The source bundle keeps identity
`sha256:625b010706dabfce5df58c036f5921af4e782da133bd27038bc442abdc79e1a4`.
The stage summary binds every remaining member; generated package/evidence
files stay ignored under `.irisx/`.

The actual wheel is installed offline into an isolated target. Its tiny real
Qwen source worker completes one CPU TTT step and four generation calls;
the other process replays four saved responses through complete-stage checks
with **zero teacher calls**. Fixture EOS annotations establish parser/stage
behavior only. WSL hides the checkout with a mount and disables networking
in a namespace. Cached WSL Torch is `2.5.1+cu121`; the Windows strict runtime
uses `2.12.1+cpu`. Transformers `5.8.1` and PEFT `0.21.0` are retained. These
environments do not establish Kaggle image parity.
The complete-worker reservation unit test substitutes a synthetic workload
to isolate terminal accounting; it supplies no model or GPU evidence.

Pending acceptance remains two-L4 runtime fit, real 4B source continuation
and candidate ranking, direct teacher yield, accepted generated pairs and ARC
quality. No promotion follows from this local draft.
