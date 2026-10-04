# Native solver owner-Editor handoff, stage 3 (2026-10-04)

Status: **review-ready; approved=false; GPU runtime unverified**.
Local `main` started clean at `c2079c9132fe855ca69e359109069e29fa6eb707`.
Resolve the delivery commit with `git log -1 --format=%H -- trials/arc-agi-2-qwen35-nvarc/native-solve-stage3-20261004.md`.
No git push, Kaggle/credential call, Dataset mutation, GPU execution, status,
log, output, retrieval, teacher, ARC correctness scoring, competition submission,
publication, new chat, goal, automation or delegation occurred.

The candidate is `.irisx/nvarc-original/runs/nvarc-original-qwen3-native-multitask-007/package-l4`.
Its run ID is `nvarc-original-qwen3-native-multitask-007`, plan digest is
`sha256:ccacce536d11058dd9d3d0b531f68a0c6e6dc1a49ba52c2bc8e263e76534abef`,
and notebook is `kernel/notebook.ipynb` within that exact package. It is an
immutable review package and must not be edited into an approved package.
The only plan differences from frozen proposal-006 are `run_id` and `kernel_id`.
All non-plan payloads, original source cells and producer files are identical.
The retained proposal-006 passes current offline preflight and stays unapproved.
The controller's c2079c9 acceptance record and all predecessor bytes remain retained.

Machine-readable delivery evidence is
[`configs/native-solve-stage3-20261004-evidence.json`](configs/native-solve-stage3-20261004-evidence.json).
Detailed local evidence is `.irisx/native-solve-stage3-20261004-001/`;
`candidate-review.json` lists exact limits, all payload hashes, native008 mounts
and SDK fields, and `preservation-final.json` closes preservation checks.

## Exact scientific and resource envelope

The checkpoint remains the original published
`sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1`, model instance `627758`,
material digest `sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03`.
The original tokenizer has sixteen symbols. BF16 rank-256/rslora/alpha-32 TTT
has 506 saved tensors and 528,564,224 trainable elements. The native008 archive
is `2a8acbc25e5f4b673e3982c550914728ddf8db350191cc4b9cf823db8014dfec`.
Its sixteen pinned distributions, Trainer/collator, schedule and optimizer are
unchanged; the target is Python 3.11.13 / Torch 2.8.0+cu128, Transformers 4.55.4,
PEFT 0.17.1, Unsloth 2025.9.7 and Unsloth Zoo 2025.9.9. No Qwen3.5,
eight-step compact pilot, teacher, new SFT, ensemble or additional task is used.

| Item | Exact bound |
| --- | --- |
| Public parents | `44f52bb0` with two tests; `833966f4` with one test |
| Source | Public training2 challenges SHA-256 `779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`; no solutions opened |
| Exposure | Previously published/tuning parents, prior training exposure unresolved; no fresh/hidden/locked holdout claim |
| Sequential processes | Normal first parent; normal second parent; first-parent fault after two updates; fresh second-parent baseline-only |
| TTT per normal parent | One complete 128-row epoch, 128 forwards and 128 optimizer steps |
| First-parent training | 15,360 input / 1,536 supervised tokens; maximum sequence 120 |
| Second-parent training | 5,632 input / 2,048 supervised tokens; maximum sequence 52 |
| Session training ceilings | 258 forwards, 258 updates, 259 reserved Trainer microsteps; 21,232 input / 3,824 supervised tokens |
| Original DFS | Cumulative NLL strictly below `-log(0.2)`; original 931-token EOS-inclusive limit; original 540-second internal clock |
| Per test | Sixteen views in four four-view DFS invocations; at most 64 processed returned sequences; 4,096 generation forwards, 128 verifier forwards, 5,242,880 physical inference input tokens |
| Verification | Original formatter/inverse/dedup/`score_kgmon`; eight views in two four-view calls per unique candidate |
| Normal inference totals | Twelve DFS invocations; at most 192 processed returned sequences; 12,288 generation / 384 verification forwards; 15,728,640 physical inference input tokens |
| Cache/reset per process | Six raw pre-TTT branch/full-prefix calls plus one post-reset call; 168 input tokens; no cache clone/crop |
| Session controls / outer forwards | 28 control calls / 672 control tokens; at most 12,958 total outer forwards |
| Hardware | Exactly four distinct BF16 NVIDIA L4 UUIDs; one sequential child on physical GPU0, other GPUs idle |
| Parent / child wall | 3,600 seconds / at most 1,000 seconds per child |
| Task / inference | 800 seconds per task / 450-second shared task inference window |
| Reserves | 300-second inference reserve, 60-second reset reserve, 240-second parent packaging reserve; at least 240 seconds before another worker dispatch |
| Disk / ZIP | At least 4,294,967,296 free working bytes; closed ZIP at most 100,663,296 uncompressed bytes (96 MiB) |
| Quota / cost | At least 2.5 reserved quota hours at the retained 2× L4 quota factor; paid USD 0; actual quota and sessions remain unknown |

The sequential per-test four-batch ordering and finite engineering ceilings are
retained explicit differences from original cross-test interleaving/historical
clock behavior. There is no full original-method or resource-sufficiency claim.

## Save preparation and genuine admission

`tools/save_nvarc_native_multitask.py` extends the successful native-solve SDK
QUICK_SAVE transport to this package. `review`, `admit` and `init` are local;
only `save` deliberately uses credentials/provider IO. The review journal has
`review_only=true` and zero reserved pushes/status/retrievals. It cannot be saved.
The installed kagglesdk 0.1.36 request was serialized offline through its real
typed schema; no mock field names substitute for its actual wire contract.

The request embeds exact payloads. It has no Dataset source, the exact official
competition source `arc-prize-2026-arc-agi-2`, exact published model version 1,
and the retained `sorokin/pip-install-unsloth-flash-patch` kernel source and
Docker digest. The parent verifies exact dependency files/versions and accepts
only the published model's explicit current or legacy mount. It requires
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2`; it opens the two embedded
truth-free public tasks. Privacy, Internet off, NvidiaL4, 3,600 seconds, slug,
title and `QUICK_SAVE` are checked again against actual SDK wire bytes.

External work is still gated by
[`AGENTS.md`](../../AGENTS.md), Decision 0010 and
[`Data and Execution Policy`](../../docs/development/data-and-execution-policy.md):
“Any external or paid execution requires explicit owner authorization”.
`stage_nvarc_native_multitask.admission_for` preserves historical v1 admission
and routes the new v2 schema through `validate_admission`. V2 binds the exact
unapproved review run/plan/notebook, c2079c9 controller review SHA-256
`2755f5c7f3498c2eef826a4e3c2cf3b0e77bd2490c48da7bef25c958a746a3a1`,
and genuine owner/controller clearance. It requires closed/reconciled sessions,
timezone-qualified quota observation, named reservation, at least 2.5 hours,
2× quota factor, USD 0, owner Editor operation and exactly one private QUICK_SAVE.
No affirmative admission was authored in this task. JSON schema validity is
not proof that its human-supplied resource facts or authorization are genuine.

Once directly authorized and supplied genuine facts, stage a **distinct**
derived identity. `nvarc-original-qwen3-native-multitask-008` is the suggested
next ID; it is currently unstaged, unreserved and unauthorized. Its only
allowed changes are identity and admission/clearance bindings. Current
construction fixes every producer/source/material/workload byte. Known native
history is checked before staging, and every save identity has one fixed package,
one journal and an exclusive fsynced reservation file.

The required v2 admission fields are listed exactly in
`tools/save_nvarc_native_multitask.py:validate_admission`; use real owner/controller
facts, never a synthetic test fixture. After approval of reviewed 007's exact
bytes as the derived 008 save, these are the commands (from repository root):

```powershell
$py = "$PWD/.irisx/nvarc-ml-venv/Scripts/python.exe"
$review = "$PWD/.irisx/nvarc-original/runs/nvarc-original-qwen3-native-multitask-007/package-l4"
$approved = "$PWD/.irisx/nvarc-original/runs/nvarc-original-qwen3-native-multitask-008/package-l4"
# $admission is the path supplied by the genuine owner/controller, not this task.
& $py tools/save_nvarc_native_multitask.py admit --package $approved --reviewed-package $review --admission $admission
& $py tools/stage_nvarc_native_multitask.py preflight --package $approved
& $py tools/save_nvarc_native_multitask.py init --package $approved
# Deliberate external action; run only under the exact direct one-save authorization.
& $py tools/save_nvarc_native_multitask.py save --package $approved
```

Reservation precedes credential/provider IO. Only one exact SaveKernel POST is
allowed, with retries disabled by the retained client. Receipt acceptance needs
version 1, the exact owner/slug URL and no invalid sources. A rejection, timeout,
interrupt, missing receipt, different slug/version or unknown outcome freezes
the identity. A process crash after reservation also forbids another save/init.
An accepted QUICK_SAVE is only a saved notebook; runtime stays unobserved.
Stop at its receipt. No run/status/log/output/retrieval/monitoring follows.

## Owner operation and independent returned-ZIP acceptance

After an accepted authorized save, the owner opens the receipt's exact URL,
confirms private/Internet off/original materials and L4 x4, then manually runs
the notebook in Editor once. The final cell displays a downloadable `結果.zip`.
If the execution cell fails, keep that ZIP/diagnostic; the independent download
cell validates the closed archive before offering it. Do not repeat Run All.
After downloading, stop the GPU session and return the complete ZIP unchanged.
A provider/parent kill can prevent packaging; missing bytes are not inferred.

Use the **actual admitted package**, never review 007, against the returned ZIP.
With `$returnedZip` set to the absolute local returned-file path, the acceptance
command is directly executable:

```powershell
$env:PYTHONHASHSEED='0'; $env:PYTHONUTF8='1'
$env:HF_HUB_OFFLINE='1'; $env:HF_DATASETS_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'
& $py tools/verify_nvarc_native_multitask.py --archive $returnedZip --package $approved --output "$PWD/.irisx/native-solve-stage3-20261004-001/returned-proof-001.json" --require-gpu-gate
```

The verifier rechecks closed ZIP/member/plan/payload/source bytes; four exact
process receipts and GPU/material identity; actual token/mask/epoch/schedule
and reservation ledgers; finite changed/reset adapter topology; all seven
completed controls per process; original DFS logits/clocks/token paths; inverse,
eight-view EOS-inclusive NLL, dedup/votes/rank; and all three tests/six export slots.
The external verifier adds independent fault-fingerprint, auxiliary GPU UUID and
parent microstep/supervised-token checks without changing producer bytes.
It requires successful normal solve processes, the sole exact Python fault after
two updates with return code 1 and verified cleanup, and a successful fresh
baseline-only process. All four initial/reset baselines must agree.

`--require-gpu-gate` returns 0 only when every qualification gate is true. It
retains a diagnostic proof and returns 2 for a valid archive with an unmet gate;
malformed/tampered evidence fails validation. Output paths are immutable: use a
new proof path for a separately justified verification, never overwrite evidence.
An inert package's admission rejection is `failed-before-dispatch`, with no GPU
work. A real hardware-gate failure is a pre-dispatch failure at its reported phase.
A qualifying complete workload has parent `failed` because its sole planned
fault remains failed; this is distinct from an unexpected failure. Empty ranks,
inconclusive output, timeouts, crashes, extra failures or incomplete resets keep
the overall gate false. Flags or file existence alone cannot qualify it.

One ranked candidate may satisfy native completeness while leaving the second
model attempt missing; the duplicate filler remains explicit. Empty tests retain
the constant filler and all denominators. Exported `submission.json` is a
truth-free structural artifact, not an authorized competition submission.

## Offline risk evidence and validation

The original DFS already applies `logits.float().cpu().log_softmax(-1)`, so
GPU logits are losslessly retained as float32 before CPU DFS replay. The
remaining numerical risk is exact Linux Torch 2.8 versus local Torch 2.12.1
CPU normalization/ordering/score behavior. Offline replay of frozen CPU005's
two-task/three-test evidence reproduced its submission and audit exactly.
A separate deterministic CPU transcript traversed deep `[0,2]`, then sibling
`[1]`, with four forwards and exact source replay. It is an immutable-prefix
fixture with no native attention/cache claim.

A real tiny random HF Qwen3 CPU model again failed the raw native deep/sibling
gate. No deepcopy/crop/rebuild was applied. Near-threshold float32 observations
are retained exactly; representational rounding can put nominal probabilities
on the same side of the strict source threshold. This is not evidence about
cross-version parity. Native GPU cache branching, nonempty trained rankings,
resource sufficiency, process isolation and cross-profile exact replay remain
**unverified** until the admitted workload returns qualifying actual evidence.
A replay mismatch must be rejected; thresholds/candidates are not altered.

Strict validation passed 36 tests with zero skips. A subsequent 13-test transport
suite also passed the actual offline v2 stage/preflight/init roundtrip and
credential-failure reservation, without credentials/provider IO. The evidence file retains
the full repository-check counts and logs. The first transport run exposed a
synthetic admission fixture mismatch while checking duplicate initialization;
it and its corrected pass are retained. The first local risk harness used an
expired synthetic clock as the real adapter deadline; its source/log are retained
and the harness was corrected. Neither failure changes scientific thresholds.
The earlier controller concurrency-associated timing failure remains retained;
its cause is still unproven. Timing suites and heavy local checks ran sequentially.
The first full check ran 504 unit tests and three validator self-tests with zero
skips, but one unchanged saved-teacher CPU fixture raised Windows `WinError 5`
at `os.replace`. Its source is unchanged from c2079c9, and one isolated diagnostic
passed without source/timeout/expectation changes. The failure is retained and
its cause is unproven. One bounded full confirmation is recorded separately;
it passed all 504 unit tests and three validator self-tests with zero skips.
There is no retry-until-green loop or new teacher invocation.

```powershell
& $py -m unittest tests.test_nvarc_native_editor_transport tests.nvarc_native_solve_strict tests.nvarc_native_multitask_strict tests.nvarc_native_multitask_archive_strict -v
& $py tools/stage_nvarc_native_multitask.py preflight --package $review
& $py tools/repository_check.py --all
```

The next required human facts are a single private QUICK_SAVE authorization for
the exact reviewed candidate's admission-only derivation, closed/reconciled
Editor/GPU sessions, observed/reserved L4 quota with timestamp/factor/reservation,
and owner/controller clearance reference. Until supplied, the delivery remains
inert. This stage establishes engineering readiness, not official Kaggle >85,
full NVARC/SOTA reproduction, method promotion or a Stage 4 dispatch.
