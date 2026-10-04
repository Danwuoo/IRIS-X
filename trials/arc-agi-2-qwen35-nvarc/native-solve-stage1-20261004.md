# Native solver engineering, stage 1 (2026-10-04)

Baseline: `5acdd9d6379cce537e8b2edb5a4b3881fd0ab491`, clean local `main`.
Delivery is the commit introducing this report; resolve it with
`git log -1 --format=%H -- trials/arc-agi-2-qwen35-nvarc/native-solve-stage1-20261004.md`.
Only local offline development and CPU fixtures were authorized. No provider,
QUICK_SAVE, GPU session, Dataset mutation, retrieval, teacher, ARC scoring,
competition submission, push, new decision or monitoring occurred.

## Repairs and review

The six tools and two tests introduced by the baseline were reviewed. The
save-only transport required no code change; its request-field tests exercise
the private QUICK_SAVE envelope without creating an SDK client or sending it.
Source cells, model material, native 008 and all previous consumed identities
remain frozen. Generation still uses the exact source DFS, `-log(0.2)`, 931
answer-token limit, sixteen views in four batches, eight verifier views and
unchanged `score_kgmon`; this is not a new method or threshold.

| Defect | Final behavior and evidence |
| --- | --- |
| First optimizer cleanup exception skipped subsequent cleanup | Independently attempt model gradients, optimizer gradients/state and accelerator references; preserve the first exception and still restore adapters. Synthetic fault injection and actual tiny PEFT success/failure finalizers verify cleanup. |
| Forward/token/deadline exhaustion became a pipeline failure and lost prior candidates | A typed planned stop yields `inconclusive`, retaining previously verified candidate votes. Interface/model/reset exceptions remain `failed`; a later parent failure overrides a child success. |
| Interrupted generation could disappear from view accounting | Reserved, completed and unfinished views are separate. A second reserved batch interrupted after the first reports 8 attempted, 4 completed and 4 unfinished views. Sparse/absent/explicitly empty EOS rows retain their denominator. |
| No-cache ModelOutput unnecessarily required a cache attribute; inconsistent cached positions passed | No-cache outputs may omit the cache; requested caches remain mandatory. Four source rows must share a bounded contiguous position range. Reservations precede model entry and failed entries remain reserved. |
| Preflight excluded every file named `stage-summary.json` | Only the root summary is excluded from its inventory; nested extra files, symlinks and mismatched run IDs fail. |
| Reader trusted ranking summaries and loosely typed work counters | Candidate token/grid/eight-score evidence is retained. The reader executes exact public inverse/parser and ranking definitions, reconstructs duplicate votes and ordering, and rejects altered inverse/ranking evidence. Forward shape, positive physical tokens, reservation/completion ordering, training tokens and terminal budgets are recounted. Inconclusive results claiming reset controls receive the same control checks. |
| Exporter accepted explicit evaluator metadata in prediction records | Known evaluator fields and truth/scored flags fail before output or input-record hashes are emitted. Each attempt slot identifies model or filler provenance. All task/test slots, indices, failures and exactly two named attempts remain. |
| Whole-task failure blocked a completed earlier test | Retain candidates only with explicit per-test `complete`/`missing-candidate` status; keep later OOM/crash tests as filler and retain the task failure in the audit. Unspecified or failed per-test statuses cannot claim candidates under a failed task. |

The original source parser's permissive parsing/truncation behavior is retained;
legal output does not prove correct solving. Export validation cannot establish
the provenance of an arbitrary grid that a caller labels as a model attempt.
A verified producer-to-exporter bridge remains required.

## Windows tempfile diagnosis

Historical `.irisx/dots-control/IRIS-LOCAL-NATIVE-OFFLINE-003`, `004`,
`IRIS-TEMP-READONLY-005` and `006` are retained unchanged. Earlier Python 3.14
could create a mode-0700 directory but failed its traversal/cleanup with
`WinError 5`; the prior token diagnostic retained four restricting SIDs.
The current same Python 3.14.7 diagnostic has an empty restricting-SID list.
Current Python 3.14 and existing Python 3.12 both create/read/write temp files;
cleanup and the complete focused tests work. No ACL, privilege, token, Python
stdlib or historical evidence was changed. These observations support an
execution-environment restriction rather than a solver defect; they do not
prove the complete causal ACL chain or repair the earlier restricted executor.

Default Python lacks optional NumPy/ML packages. The existing
`.irisx/nvarc-ml-venv/Scripts/python.exe` supplies Torch `2.12.1+cpu`,
Transformers `5.8.1`, PEFT `0.21.0`, NumPy `2.3.5`. It completes the exact-source
fixtures and the separate strict native module. No installation was needed.

## Validation and inert package

Exact commands, durations, exit codes, source/artifact hashes and preserved
failure logs are bound in [the evidence record](configs/native-solve-stage1-20261004-evidence.json).
All outputs are under `.irisx/native-solve-stage1-20261004-001/`.
The record promotes hashes and observations, not ignored files into authority.

| Check | Result |
| --- | --- |
| Focused native/export regressions, existing ML venv, exact code fixture | 54 tests, no skips |
| `tests.nvarc_native_solve_strict` | 4 actual tiny Qwen3 CPU tests, no skips |
| Full `tools/nvarc_ml_profile.py` | 63 actual ML tests, no skips; 543.449 test seconds |
| Remaining legacy optional SFT/TRM tests | 2 tests in the ML venv, no skips; ML class/distributed covered in the strict profile |
| Final `python tools/repository_check.py --all` | 459 tests, 14 optional skips; 222.440 test seconds; validator/invariants/whitespace PASS |
| Actual inert stage, preflight and locally relocated parent | `003` is unapproved; admission gate rejects before dependency/model work, and the closed failure archive verifies with zero generations/steps/forwards |
| Frozen material | 64 historical files rehashed; final preservation receipt is bound in evidence record |

The default interpreter's 14 skips are ten native exact-source tests without
NumPy and four legacy optional groups: Torch SFT, distributed, the ML class and
TRM saved-tensor normalization. The ten pass in the focused ML-venv run; the
ML class/distributed pass in the strict profile, and the remaining two pass in
`optional-recovery`. There is no unexecuted local CPU skip in those groups.

The new final identity is `nvarc-original-qwen3-native-solve-003`, under
`.irisx/native-solve-stage1-20261004-001/proposal-003/`:
plan digest `sha256:b7fc018341bcee06a65ce1bb6cea2505ba069bc164d78835072f6a9032ba679b`,
`approved=false`. The locally produced admission-rejection archive digest is
`6eda2cce4a34fc97f8302d457560ad278a5b1f05299125a1355c6d238ea9744a`;
it contains three members and proves no trained solve.
New inert `002` retains its earlier bytes and is superseded by `003` after the
unfinished-view correction; original `001/proposal-001` was never overwritten,
approved or repurposed. No save journal exists for either new proposal.

The independent replay harness initially failed importing `tools` because it
was outside the module search path. Its exact failed script/log are retained;
the corrected local harness sets repository/src paths. The first strict CPU
attempt also exposed mutable HF cache contamination. The final strict module
explicitly checks that rejection and separately emulates isolated caches for
real-logit/reset tests. No fallback was added to the runtime.
The first 457-test repository pass predates the final denominator regression.
The next 458-test run failed only because this report linked its evidence JSON
before that file was written; that failure is retained and the complete check
is rerun after the linked record exists.

## Recompute locally

Run from the repository root in PowerShell:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONHASHSEED='0'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:HF_DATASETS_OFFLINE='1'
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
$env:IRIS_NATIVE_CODE_ONLY_DIR=(Resolve-Path .irisx/native-solve-stage1-20261004-001/code-only).Path
& .irisx/nvarc-ml-venv/Scripts/python.exe -m unittest tests.test_nvarc_native_solve tests.test_arc_kaggle_submission -v
& .irisx/nvarc-ml-venv/Scripts/python.exe -m unittest tests.nvarc_native_solve_strict -v
& .irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py
python tools/repository_check.py --all
python tools/stage_nvarc_native_solve.py preflight --package .irisx/native-solve-stage1-20261004-001/proposal-003
python tools/verify_nvarc_native_solve.py --archive .irisx/native-solve-stage1-20261004-001/inert-work-003/結果.zip --package .irisx/native-solve-stage1-20261004-001/proposal-003 --output .irisx/native-solve-stage1-20261004-001/independent-proof.json
python .irisx/native-solve-stage1-20261004-001/preserve.py after
```

Use a fresh output filename for each independent proof. To re-stage, choose
another unused run ID and new directory; never rewrite a retained proposal.
The code-only source fixture consists of the three exact public cells listed
in `SOURCE_HASHES`, extracted locally from frozen inputs, without acquisition.

## Stage 2 handoff: published ARC-SFT weights and full native solver

The current GPU proposal deliberately admits one source-exposed development
task with one test. `validate_visible` rejects a second task or test;
`source_batches` admits one sixteen-view group. Upstream splitting alone does
not provide a complete multi-test runtime. The exporter independently supports
all challenges and tests, including every failure status, but is not wired to
this native result schema. Native `complete` means bounded nonempty computation;
one candidate still leaves an exporter model-attempt slot missing and requires
explicit filler accounting, not a `complete` two-model-attempt record.

The strict tiny CPU tests establish a second task's seeded adapter baseline,
discarded optimizer/gradients and bitwise reset prefill after both success and
failure. They use FP32/rank-2 synthetic PEFT and a cache-isolation fixture.
They do not qualify original BF16/rank-256 Unsloth, two full native epochs,
all RNG/scheduler/process state across real tasks, 4B cache numerics or runtime.
Native 008's prior training-only observation remains separate.

Stage 2 needs a reviewed full solve loop using the pinned published ARC-SFT
checkpoint, actual native cache and numerical controls on the target backend,
nonempty candidate/ranking/reset evidence, then second-task isolation. Extend
task/test scheduling, finite budgets and terminal records under a distinct
envelope; share one task-local TTT across that task's test inputs and keep every
unexecuted/timed-out test in the exporter. Bind the producer, candidates and
submission audit; keep evaluator truth outside solver/outbound. These are
future engineering/authorized-execution gates, not a request to reproduce SFT
before using published weights. Historical native-clock/method parity and
independent quality measurement remain separate. This stage makes no accuracy,
official-score, SOTA, clean-evaluation or full-reproduction claim and stops here.
