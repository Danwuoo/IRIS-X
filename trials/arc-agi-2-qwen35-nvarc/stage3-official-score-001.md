# Stage 3 single official CLI score

Date: 2026-10-05 (Asia/Taipei). Status: **acceptance completed; official submission 56840442 failed with notebook exception and no score; private-run retention qualification remains partial**.
Authority: [Decision 0059](../../docs/decisions/0059-obtain-one-official-stage3-cli-score.md).
Stage 4 remains unopened. Paid cost ceiling is USD 0. Existing consumed 007–010
packages, receipts and returned observations remain immutable. The 010 engineering
export is only two public parents/three tests and is not the official candidate.

The distinct intended candidate is `nvarc-stage3-official-001`, private kernel
`danielwuu/nvarc-stage3-official-001`. Resolve the implementation commit with
`git log -1 --format=%H -- tools/stage_nvarc_official.py`. Candidate/producer hashes
will bind its exact implementation bytes before its first provider write.

## Current primary sources and CLI

The [official overview](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview)
requires a notebook, Internet disabled, at most 12 hours GPU runtime and
`submission.json` with two named attempts for every actual task/test in input
order. It provides L4 x4 machines and states a 2x quota rate, subject to change.
The [official rules](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules)
allow one submission per day. Account submissions were read through CLI and
returned `No submissions found`. Listing competition files identified
`arc-agi_test_challenges.json`; only that challenge file was downloaded.
Solution filenames were listed but their bytes were not opened or downloaded.

Installed official Kaggle CLI is **2.2.4** at the Python 3.12 installation's
`Scripts/kaggle.exe`. Its help and implementation verify code competition
submission through `competitions submit <competition> -f submission.json
-k <owner/slug> --version 1 -m <description>`. This binds notebook rerun and
output filename; it is not a local JSON upload. The long version flag avoids
the client's global short `-v` verbosity handling. Existing credentials remain
outside command arguments and retained evidence. Default requests sessions have
no configured mutation retries. A process timeout has an unknown outcome and
consumes its exclusive reservation.

## Full-input finite budget

The official visible preview contains **240 tasks and 259 tests**. Offline
public-only native material preparation produces **30,720 optimizer steps**,
**35,347,968 training input tokens**, with maximum sequence length **5,598**.
Actual hidden rerun tasks and multi-test counts are read afresh at runtime;
no preview task IDs or test answers are embedded. A runtime task plan and input
digest bind every actual task/test. Infeasible full-input plans fail explicitly
rather than intentionally excluding most tasks.

| Bound | Allocation |
| --- | --- |
| Whole notebook | 42,600 seconds (11h50m), below the official 12-hour cap |
| Shared initial preparation | At most 600 seconds |
| Final strict CPU export | 1,800-second reserve/ceiling |
| Hardware | Exactly four distinct BF16 L4 UUIDs; four independent lanes |
| Fresh per-task preparation | 120 seconds |
| Full task-local training | One unchanged 128-step epoch; 100 seconds + public training tokens / 800 |
| Inference | 180 seconds for each actual test, four batches/sixteen views |
| Reset reserve | 60 seconds per fresh task process |
| Per-test limits | 4,096 generation forwards, 128 verifier forwards, 5 MiB physical input tokens, at most 64 processed sequences |
| Original source rules | 8,192 context, 931 EOS-inclusive answer tokens, cumulative NLL strictly below `-log(0.2)`, original inverse/dedup/eight-view `score_kgmon` ranking |
| Longest preview child | 1,356 seconds |
| Working disk | At least 10 GiB free |

The training estimate uses the prior measured native long-task epoch:
955,392 input tokens in 862.043 seconds. Reserving 800 tokens/second plus
100 fixed seconds is more conservative than that measured token rate, but is
not a sustained throughput guarantee. Public token/test costs alone determine
longest-job-first allocation. All preview tasks are assigned exactly once;
four reserved lane totals are **39,527 / 39,530 / 39,529 / 39,531 seconds**,
below the 40,200 seconds remaining after both common reserves. No task is
selected using an answer, score or inferred difficulty.

Each fresh subprocess loads the unchanged published
`sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1` and exact retained
dependency/source bytes. It binds its assigned hardware UUID, public collator
rows and complete native schedule, and retains before/after adapter inventories,
cache controls, optimizer cleanup, reset and durable test transcripts. Separate
working directories prevent concurrent generated trainer cache writes. Planned
fault-first/baseline-only probe work is removed. After a partial test search or
ordinary local exception, later tests receive their own clock and denominator.

These explicit engineering deviations are retained: four parallel fresh task
processes, public-cost dispatch order, per-test clocks/forward limits and the
fresh startup seed-0 CPU export. The scientific DFS threshold and original
TTT scalar recipe are unchanged. The runtime export replays exact transcripts
with its own pinned Torch 2.8 environment; local cross-Torch portability remains
unverified and is not upgraded by an official score. The frozen candidate's
quota and session closure fields remain null/unavailable. A later, separate
read-only `kaggle quota --format json` observation at 2026-10-04
18:04:07.864 UTC / 2026-10-05 02:04:07.864 Taipei reports GPU **4.25h used,
25.75h remaining, 30.00h total**, with raw refresh string
`2026-10-10T00:00:00` (no timezone supplied). At the published 2x rate,
the 11h50m private runtime cap would consume at most 23h40m. This observation
does not provide a reservation ID or establish closure/reconciliation of other
sessions. It is retained separately from the unchanged candidate and launch.

## Submission guard and evidence

`tools/run_nvarc_official_cli.py` reserves immutable package/manifest/command
bindings before the private CLI kernel push and before the one formal CLI
submission. A rejection, timeout or interruption cannot cause a blind repeat.
The formal command requires exact version-one acceptance, strict exported
preview output, all task epochs/tests launched and reset verified, complete
two-slot output and explicit model/filler accounting. Sole candidates are
duplicated; a truly missing candidate uses the exporter's marked constant
fallback. Neither is claimed as a second model prediction.

The final account submission read occurs before reservation, protecting the
daily slot. Backed-off CLI status/score reads will retain the formal ref and
actual public/private score fields. Preview coverage never proves hidden-rerun
coverage. An accepted formal submission consumes the one-score attempt even
if it terminates without a score; a numeric 0 is a valid terminal score and
does not authorize a second submission.

Local evidence is retained under
`.irisx/stage3-official-score-20261005-001/`, including initial read outputs,
the public preview budget, offline full-input preflight and first test logs.
The offline preflight passes all 240-task/259-test allocations in 81.625
seconds with zero external calls. Full repository validation passes three
helper tests and 510 unit tests in 370.967 seconds; its one optional source
fixture class was initially skipped because the explicit fixture environment
was absent. All ten omitted source tests then pass separately with the retained
hash-bound code-only fixture, giving 520 unit tests covered. Initial logs and
the skip remain retained. Timing checks ran separately from heavy material
preparation. Exact production package staging passes against source commit
`6b26925d09a5f6a0180012efe0374a49fd024308`. Candidate digest is
`sha256:9c23325a7eec8158c145c922d46512b1287a003ec423db5ea85932b9d95816b9`.
The reserved CLI push was accepted as private version 1 at
2026-10-04 17:47:23.840 UTC / 2026-10-05 01:47:23.840 Taipei:
[exact kernel](https://www.kaggle.com/code/danielwuu/nvarc-stage3-official-001).
Its command, wire-script/package hashes and receipt are retained in
[`stage3-official-score-001-kernel-launch.json`](configs/stage3-official-score-001-kernel-launch.json).
The first read at 17:48:50 UTC reports `KernelWorkerStatus.QUEUED`.
Read 014 at 2026-10-04 20:40:01.300 UTC / 2026-10-05 04:40:01.300
Taipei reports `KernelWorkerStatus.RUNNING`, after earlier reads remained
queued. A read-only diagnostic log request at 19:24:28.495 UTC returned only
an empty line; that observation does not establish zero model work.
No formal competition submission is reserved or sent and no official score
exists yet. Provider `RUNNING` alone does not verify the hardware, task epochs
or exported output. Current provider-read bindings are retained in
[`stage3-official-score-001-progress.json`](configs/stage3-official-score-001-progress.json).
The local foreground continuation was bounded to 80 status reads/20 hours
for each provider phase and was not a recurring automation. Its script hash
and the separate quota observation are retained in the launch evidence
configuration. The owner subsequently instructed `先停止監看`. At
2026-10-04 23:17:03 UTC / 2026-10-05 07:17:03 Taipei, both local Python
processes for this continuation were stopped and zero remaining helpers were
verified. The local session exited with code 1 because it was stopped; this
is not a Kaggle runtime failure.

The last provider read is 024, at 23:10:20.059 UTC / 07:10:20.059 Taipei,
and reports `RUNNING`. At the owner's stop, current Kaggle state was unqueried.
No provider cancellation, subsequent provider query, terminal retrieval
or formal submission had occurred. No formal reservation or receipt existed and no
automatic submission path remains active. Monitoring/automatic continuation
will not restart without owner direction. The stop and all retained reads are
bound in the progress configuration; Stage 4 remains unopened.

## Completed owner-submission acceptance

The owner reported completion and their own competition submission, then
supplied the error screenshot. It explicitly identifies
`nvarc-stage3-official-001 - Version 1` as **Notebook Threw Exception**.
The official SDK detail for ref **56840442**, read at 03:57:39.058 UTC /
11:57:39.058 Taipei, confirms an unhandled error during the competition rerun.
Both official scores are null; CLI score fields are empty. Its `COMPLETE`
status describes terminal processing, not successful scoring. The one formal
attempt is consumed and **official score acceptance failed without a score**.
This is not score zero. No further official polling, retry, submission or GPU
run is authorized by the failure, and none was performed during acceptance.

The API and screenshot expose no traceback, hidden input identity, hardware
inventory or completed workload for the scoring rerun. The generic warning
that hidden data can differ does not identify its root cause. Actual hidden
model work remains unobserved; neither zero work nor completion is inferred.
The screenshot establishes the notebook/version association, while independent
download of the submitted bytes returned HTTP 403. The returned private
`submission.json` is verified separately below.

Exact evidence, failure receipts and SHA-256 bindings are retained in
[the acceptance configuration](configs/stage3-official-score-001-acceptance.json).
The immutable implementation is commit
`6b26925d09a5f6a0180012efe0374a49fd024308`; the candidate digest remains
`sha256:9c23325a7eec8158c145c922d46512b1287a003ec423db5ea85932b9d95816b9`.
Provider version 1's cell programs and all returned producer programs match
the approved bytes. No notebook, Dataset or solver implementation was changed.

The completed **private preview run** has `export-complete` terminal outcome,
four assigned distinct BF16 L4 UUIDs, Torch 2.8.0+cu128 and CUDA 12.8, and
21,681.367 seconds elapsed (**6h 1m 21.367s**). Its receipt digest and root
copies of the summary, terminal and submission verify. This is distinct from
the failed competition rerun.

| Independently checked private-run observation | Result |
| --- | --- |
| Public-only runtime plan and native collator tokens | All 240 task epochs rebuilt; all retained tokens match |
| Full training work | 30,720 training forwards/backwards and optimizer steps; 35,347,968 input tokens |
| Test denominator | All 259 tests started; no task intentionally skipped |
| Exported attempt fields | 372 model slots; 146 duplicate-first filler slots; 518 total |
| Candidate coverage | 113 tests have two model attempts; 146 have one; no constant fallback |
| Source search completion | 219 native-complete tests; 30 source DFS deadline stops; 10 inference deadline stops |
| Worker outcomes | 202 complete; 38 inconclusive; no worker failure or deliberate fault |
| Actual inference forwards | 1,680 control; 217,301 generation; 1,312 verification |
| Ranking verification | 5,240 ranked verifier rows bound to exact transformed input/answer tokens and EOS-inclusive scores |
| Reset evidence | 237 complete before/reset tensor comparisons; all 240 post-reset prefill controls and optimizer cleanup records checked |

The independent local audit reconstructs every task event/checkpoint envelope
and obtains exactly the retained native-evidence digest
`sha256:99c881c40cca3e4252aa5740b5148a91911f92edc484a7d576bbfca40c63abc0`.
Parsing, inverse views, deduplication, verifier bindings and source ranking
reconstruct the complete submission and audit exactly. Submission SHA-256 is
`0772c3f5a8a5ac92e1947e3f8b2a5213d8c435f72effdc71328492baf888c875`;
audit SHA-256 is
`bac6cdebf1e8a50649037efdfa02972074818774149287ebed1792b82a868130`.
No test answers were opened and no local correctness score was computed.

Artifact qualification remains **partial**. Of 5,080 selected evidence files,
5,077 are retained with verified hashes. Three startup baseline inventories
remain unavailable: `17b866bd`, `264363fd` and `39e1d7f9`. Their training
ledgers, prepared tokens, changed trained/reset inventories and post-reset
numerical controls are present, but an independent complete before/reset
tensor claim for those three tasks is not made. Subsequent output catalog
reads, including explicit version 1, returned HTTP 403
`Permission 'kernels.get' was denied`. Initial local path assertions, stopped
CLI transfer, truncated ZIP, 404 and 429 reads remain retained. Five complete
entries recovered locally from the truncated ZIP passed their individual
size/CRC checks; the ZIP as a whole remains unverified.

The recorded strict fresh seed-0 export succeeded in the Kaggle runtime.
Local forensic ranking reconstruction explicitly skips the separate strict
cross-Torch DFS numeric replay. Its indexed observation join preserves the
same uniqueness/order predicates, with original/indexed results equal on
the first task. No tolerance or production verifier was changed.
**The strict portable GPU gate remains false**, and the three retention gaps
also prevent a full independent native training/reset qualification.
Neither official acceptance, correctness, hidden coverage nor method promotion
is inferred from the private preview.

Repository invariants and whitespace checks pass. The initial full-suite
attempt used system Python without `tokenizers` and reported three errors,
eight failures and 27 skips across 491 tests; some Windows readiness fixtures
also failed in that concurrent run. The dependency/process cause was not
fully isolated. Focused reruns passed 42 native transport/admission/multitask
tests in the ML environment, three export tests, and 11 process tests with
the correct source path. The first full-suite failure is retained; a new
all-suite pass is not claimed. Tiny CPU unit fixtures are not native GPU
qualification. No new external model calls, paid work, formal submission,
automation, Stage 4 or Git push occurred. The earlier stopped continuation
remains stopped.
