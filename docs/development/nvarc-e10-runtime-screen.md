# E10 caller transport and offline screen

Decision 0061 governs this new continuation. Historical native/public stagers,
run identities, research draft and evidence remain unchanged. This implementation
has synthetic/process validation only; real SFT139 GPU completion, resource
feasibility, observation overhead and E10 quality are not established.

## Delta

The accepted local E10 repair already supplied allocation v1, schedule v2,
FIFO/eight-view strict replay and admission-bound E01 recovery. It deliberately
left the legacy export CLI without admissions and deferred real packaging shut.

New additive modules supply:

- `nvarc_allocation_transport.py`: one inherited local socket per native task
  process, an independent coordinator clock/deadline, a durable caller map and
  admission chain, and closed bounded requests/replies
- `stage_nvarc_e10_screen.py`: new material/partition/config-bound offline
  notebook and exact private metadata; no provider operations
- `nvarc_e10_screen.py`: finite four-lane fresh-task native execution, six
  included control calibration jobs, strict CPU calibration replay, and four
  final CPU exports under one session cap
- `verify_nvarc_e10_screen.py`: independent read-only CPU replay and committed
  projection verification against separately retained package/caller hashes

`nvarc_native_export.py` adds explicit caller receipt path/hash and read-only
validation options. The old Python allocation argument and legacy CLI behavior
remain: deferred evidence without an independent admission input fails closed.

## Caller boundary

The coordinator assigns a socket to one task binding and fixes its common
task/session epoch deadline at dispatch. The worker requests only the next
actual integer test index with that binding's digest. It cannot provide a start,
deadline, duration or allocation. The parent reads its own host clock at actual
test dispatch, appends/fsyncs the closed admission chain and publishes its map
before returning the allocation. Duplicate, foreign, out-of-order, oversized,
non-finite, malformed and expired admissions fail closed.

The unchanged derivation is:

```
verification = min(caller start + 30, caller common deadline)
generation = max(caller start, verification - 10)
```

Both schedules use these same values. Every real test gets an independent
admission, including after an ordinary partial generation/verification result.
A later unexpected exception preserves earlier committed tests and the complete
denominator. It does not publish that failed test's uncommitted candidates.
There is no candidate-specific fresh allowance. An admitted forward may return
late; host clocks cannot preempt CUDA or blocking IO.

The parent freezes its own in-memory receipt after confirmed producer stop.
It passes the receipt path and its independently retained SHA-256 into a fresh
CPU interpreter. Native deferred replay reconstructs the FIFO, tokens, NLLs,
all original occurrence votes and ranking. An additive caller gate also binds
the interleaved arm's source cutoff and terminal telemetry, including killed
prefixes. Coordinately changing worker evidence and rehashing it cannot extend
the unchanged caller admission. Changing the independent caller pin crosses
the trust boundary. The shared OS, receipt hashes and host epochs are not a
physical GPU clock, authentic model execution or tamper-proof OS attestation.

## Materials and immutable build

The builder consumes the three exact code-only files in `SOURCE_HASHES`, the
reviewed `inspection_helpers.py` and `hardware_helpers.py`, source/model byte
inventories, small exact tokenizer, original native configuration and 129 scalar
rates for the 128-step epoch. It verifies the unchanged research baseline's model, PEFT,
training-argument, checkpoint-flag and learning-rate digests. Model weights are
mounted from the exact published SFT139 model, never embedded in the notebook.

The original native model/preparation prefix is taken from the tracked
`nvarc_original_native_ttt_worker.py`. The native renderer supplies its new
full-epoch/inference/reset tail. The assigned-rank bridge is derived with the
existing reviewed bridge renderer. Exactly one main block survives; the old
complete-training run body is removed. No frozen notebook's raw runner or
answer lookup is substituted for a missing code-only fixture.

The production CLI requires every included local implementation file to match
the supplied full Git commit. The package manifest hashes the complete closed
inventory. Preflight reconstructs the source/config/budget/workload/notebook and
private offline metadata from the current implementation; callers should also
provide the separately retained package-manifest SHA-256. Changed bytes require
a new identity. Existing package/runtime directories are never overwritten.

The frozen visible partition includes whole tasks and every actual test.
Canonical challenge-map order is used for the native denominator, while the
separately frozen development order governs workload/calibration order. Only
task IDs, visible hashes, development order and an opaque source-partition hash
enter the runtime partition. Strata and evaluator diagnostics are not packed.
Task material is stored separately per task to keep every decoded payload below
8 MiB and avoid repeatedly reading the entire screen's training text.

The provided development slice is 24 tasks / 35 actual tests. Once exact native
material is available it produces 96 task-runs / 140 test-runs. These are exposed
public development data; no fresh holdout or official denominator is implied.

The restored alternative material closure passed exact model/config/source/
tokenizer verification and totals 62,097 bytes, excluding weights. CPU source
preparation with Python 3.12.14 / NumPy 2.3.5 / tokenizers 0.21.4 derived all 24
full epochs in 13.16 seconds without importing Torch or invoking a model. The
package records those versions explicitly; the native runtime remains pinned
to NumPy 2.2.6 and must compare every actual collator row. The exact historical
two-task challenge artifact for an additional cross-version parity check was
absent at the requested path; no alternate same-ID task was substituted.
The subsequent repository-pinned training2 challenge source matched SHA-256
`779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5`.
After strict truth-free schema validation, its exact two-task projection matched
the native007 challenge digest. Both tasks' full 128-row, text and token digests
then matched the retained native007 references exactly under NumPy 2.3.5. That
two-task CPU parity resolves this targeted preprocessing check; it is not all-
development GPU preprocessing or a native model/replay qualification.

## Bounded runtime

The two schedules each receive two same-seed technical repeats. The first six
interleaved repeat-1 tasks are calibration jobs included in the 96-task ceiling.
No later control/comparative task is dispatched until all six finish their
native process/source/reset/host-observation gate and a fresh CPU strict replay.
Failed or missing calibration replay refuses candidate dispatch. No extra
calibration model runs or automatic task retries are introduced.

Each task uses a fresh native model/Trainer process on its fixed physical rank;
both arms share that choice. This reuses the existing fresh-task native toolkit,
rather than claiming equivalence to the lighter persistent public worker.
Source DFS, floor 0.2, 931-token ceiling, full 128-row/step epoch, full-task view
stream, inverse transforms, score reuse, votes and `score_kgmon` are unchanged.
Detailed profiling is off. Exclusive host phases retain explicit unobserved
values; they are not GPU-kernel durations or summable across workers.

The three-hour plan declares one 10,800-second session, four L4s, USD 0, a 12
allocated GPU-hour upper bound, 1,500 seconds finalization: 1,200 seconds for four final CPU exports (300 seconds
each), 120 seconds cleanup and 180 seconds archive, 20 GiB free working storage and an 8 GiB uncompressed evidence cap.
The included calibration CPU replay is also bounded at 300 seconds.
Task reservations use 120 seconds fresh preparation, `100 + demo tokens/800`
seconds training, 30 seconds per actual test and 60 seconds reset. These are
engineering hard allowances, not measured throughput. An admitted production
plan rejects lane reservations that exceed the session minus final exports
and calibration replay. Ordinary exhaustion leaves undispatched jobs explicit.

Actual preprocessing established 22,961,408 total training input tokens over
the 96 task-runs. The four conservative lane reservations are 14,948 / 14,972 /
14,944 / 14,960 seconds. They do not fit the three-hour envelope, which is
retained as inert rejected-plan evidence. A separately named five-hour planning
identity uses 18,000 seconds and 20 allocated GPU-hours. After 900 seconds
initial setup, 300 seconds calibration CPU replay and 1,500 seconds finalization,
each lane has 15,300 seconds: 328 seconds above the maximum reservation.
This is a feasible bounded plan, not measured throughput or permission to launch.

Exact optimizer/token/forward/processed-sequence ceilings are computed from
the selected tasks. The real resource admission must name this new screen,
record available free quota and its multiplier, provider session limit, current
observation time, reconciled prior sessions and source/license/rules review.
The coordinator must check these facts before launch. Package preparation alone
does not establish their truth, acquire quota, submit a kernel or accept terms.
The unambiguous admission field `allocated_gpu_hours_per_quota_hour` states how
many allocated GPU-hours correspond to one charged quota hour. Required free
quota is allocated GPU-hours divided by this verified ratio: 20 / 2 = 10 quota
hours for the five-hour plan if that ratio is actually observed. An earlier
unexecuted prototype inverted this calculation; it was corrected before any
resource admission or GPU launch.

The local execution ledger records launch reservations before Popen and retains
terminal failures. It is not the coordinator's provider submission ledger and
does not grant a provider retry. Native workers have a parent-death guard.
Cleanup requires confirmed producer stop before caller freeze/archive. Earlier
committed candidates remain available after later failure, while failure is
reported separately from schema-valid output and strict evidence.

## Commands

Prepare a `irisx/native-code-material-contract-v1` JSON with exactly
`files_sha256` (the seven source/inventory files), `template_sha256`,
`tokenizer_sha256` and truth-free `source_provenance`. The tokenizer is separate
from those seven files. A runtime resource admission uses format
`irisx/stage4-free-gpu-resource-admission-v1` and the exact fields checked by
`validate_resource_admission`. Omitting it builds an inert package; the notebook
refuses execution. A current verified admission plus a new identity is needed
for a runnable package.

```
PYTHONHASHSEED=0 PYTHONPATH=src python tools/stage_nvarc_e10_screen.py stage \
  --package NEW_PACKAGE --screen-id stage4-e10-screen-NEW_ID \
  --session-seconds 18000 \
  --source-commit FULL_REVIEWED_COMMIT --materials CODE_ONLY_MATERIALS \
  --material-contract MATERIAL_CONTRACT.json --template ORIGINAL_NATIVE_PLAN.json \
  --tokenizer EXACT_TOKENIZER.json --challenges SOLVER_VISIBLE_DEV_CHALLENGES.json \
  --partition FROZEN_VISIBLE_PARTITION.json --resource-admission NEW_RESOURCE_ADMISSION.json

PYTHONHASHSEED=0 PYTHONPATH=src python tools/stage_nvarc_e10_screen.py preflight \
  --package NEW_PACKAGE --expected-manifest-sha256 RETAINED_PACKAGE_MANIFEST_SHA256

PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= PYTHONPATH=src \
  python tools/verify_nvarc_e10_screen.py --package NEW_PACKAGE --runtime RETAINED_RUNTIME \
  --expected-package-manifest-sha256 RETAINED_PACKAGE_MANIFEST_SHA256 \
  --expected-caller-bindings-sha256 RETAINED_CALLER_BINDINGS_SHA256
```

The verifier runs four `--validate-only --verify-committed` native CPU exports.
Each final runtime export and each committed independent replay requires native
epoch/source/reset/host gates for all actual 24 tasks, including empty candidate
pools. The producer and verifier use the same bound plan task order and full
mandatory-gate export context. The earlier first-six gate still controls the
dispatch barrier, and a separate external first-six replay remains retained.
Missing or failed non-control qualification rejects the final comparative export;
the original native evidence bytes remain available for failure diagnosis.
It verifies static source/config/input against the outbound package, caller
admissions and committed projections without invoking a model or republishing
outputs. It reports the runtime outcome separately. Correctness scoring remains
local in the evaluator quarantine; no evaluator or solutions enter this runtime.
Research acceptance/kill thresholds are unchanged. No development outcome grants
promotion or substitutes for official scoring; no official submission command
is executed by these modules.

## Standalone finalized-archive download

New probe/screen builds add a separate, self-contained download-only cell. The
main scientific/supervision cell and archive producer are unchanged. The cell
contains build literals for the exact run ID, SHA256 of canonical `screen.json`
and existing uncompressed archive cap: 1 GiB for a probe, 8 GiB for a screen.
It can run independently of main-cell globals or success, so a valid finalized
failed-run diagnostics ZIP remains retrievable.

Only `/kaggle/working/<exact-run-id>.zip` is read. No directory enumeration,
archive creation, extraction, recovery, CPU re-export, model/source/dependency
import, training, GPU work, install/uninstall or new scientific work occurs.
The cell uses stdlib validation and imports `IPython.display` only afterward for
a download link. It refuses a missing/temporary/truncated archive, wrong run or
plan, symbolic links, non-regular files, unsafe/duplicate member paths, special
file metadata, encryption, unsupported compression, malformed closed end records
and failed CRC/size/compressed-EOF checks. Existing atomically published ZIP64 archives are
supported. Central-directory bytes are bounded to 16 MiB before `ZipFile` parses
them; count is capped at 50,000, plan bytes at 8 MiB, total uncompressed bytes at
the unchanged archive cap, and stored archive bytes at that cap plus 64 MiB.
Every member is read in 64 KiB chunks; bytes are never executed or extracted.
Stored entry sizes must match. Deflated entries additionally require the stdlib
`ZipExtFile` decompressor to report EOF with no unused or unread compressed
bytes; if that internal state is unavailable, validation fails closed. CRC and
uncompressed length alone can accept an output-complete truncated stream.

This establishes bounded archive integrity and exact embedded run/plan identity.
It does not validate all native scientific evidence, qualify notebook exit or
imply promotion. Retained interrupted member files stay unqualified evidence;
the download cell does not relabel or rebuild them. Prior probe004/screen005
archives/notebooks and historical successful/failed identities remain unchanged.

New probe/screen packages also include deterministic inert `cli-handoff.json`.
It requests `kaggle kernels push -p kernel -t 1800` for a probe, `-t 18000` for
a selected five-hour screen, or `-t 10800` for a selected three-hour variant.
Official CLI 2.2.4 consumes an integer timeout as `session_timeout_seconds` in
**seconds**; `machine_shape=NvidiaL4` metadata remains sufficient. Provider cap
and internal watchdog fields are distinct; no budget magnitude changes. Static
source/parser checks establish requested semantics, not server enforcement.
CLI push saves and runs, whereas historical QUICK_SAVE-only authority does not.
All handoff commands remain inert pending current admission and exact review.

Exact preflight now reconstructs the download cell and CLI handoff and rejects
extra package members even after local hashes are recomputed. The shared helper
is included in probe/screen snapshots and in the candidate's build/runtime
snapshot because the candidate imports the shared screen stager.

## Validation status

New unit tests use fixed fake models/clocks or explicit fake subprocess scripts.
Their GPU/native-material claims remain false. Coverage includes real socket
IPC, multiple-test admissions, late refusal, coordinated rehashed mutations,
baseline deadline binding, missing/failed calibration replay, launch failure,
cleanup, full denominators, package reconstruction and private metadata tamper.
Independent-verifier orchestration tests use fake subprocess results and do not
claim to have completed real native replay.

The earlier focused observation ran 73 tests: 44 passed, 28 optional tiny-ML/
native-material cases skipped, and one historical baseline test errored because
Git object `90ea1bcd40d9e8c88fb7e849e55257704e9b3c16` was absent. After the
coordinator restored that exact object/blob, that specific test passed unchanged.
The original error remains recorded. No full-suite PASS or native/GPU readiness
claim follows from this. The final focused command ran 69 tests: 68 passed and
one real tiny native source/recovery case skipped for unavailable retained
native test fixtures. The verified source/material closure and tokenizers are
available; CPU Torch installation is blocked by the recorded provider/proxy
failure and is not retried through another route. Real tiny/native replay,
all-task native collator confirmation, actual free quota/hardware and GPU timing/
quality remain explicit blockers or pending observations.

## Independent runtime review and repair

The frozen eca76a3 independent review identified real gaps: a blocking outer
stdout supervisor, unclosed archive membership, zero-candidate calibration
skipping mandatory epoch checks, stale/future quota acceptance, an untyped
receipt-head field and basename-only manifest exclusions. Those failed
counterexamples remain preserved; initial PASS tests did not cover them.

The repair uses deadline-authoritative outer process-group supervision without
blocking stdout reads or waits. The original notebook start is authoritative,
including material setup, calibration, exports, cleanup and archive. A late
calibration callback cannot unlock comparative dispatch. Process exit that is
not confirmed at the cap remains failure; this is not a physical GPU-preemption
or tamper-proof OS claim. Static payload filesystem IO before launching the
supervised child still relies on the host filesystem, and a startup that has
already exhausted the allowance refuses model-process launch.

Archive membership is closed to exact static payload and named runtime/native/
generation artifacts; compiler caches are omitted. Unknown files, symlinks,
changed static bytes and evaluator markers in structured artifacts reject the
archive. The independent verifier repeats this membership check. Only the exact
root package-manifest path is excluded from its own inventory.

Calibration validate-only replay now receives an explicit mandatory task list.
For every control task, including empty pools, it independently checks native
source/epoch, optimizer construction/completion, full source-row/token multiset,
optimizer LR against the same-platform scalar schedule (the existing four-ULP
reference bound is unchanged), baseline/trained/reset inventories, reset
control, closed host phase partition and every replayed test telemetry record.
The legacy empty/filler native export path is not globally changed.

Actual runtime admission requires quota observation within one hour of the
coordinator clock and at most five seconds in the future. Historical read-only
preflight/replay does not renew that admission. Receipt heads must be typed
SHA-256 digests. These guards still need independent counterexample rerun and
real native/GPU validation before readiness.

## Barrier-budget correction

The earlier five-hour lane-only fit statement was independently disproved:
first-six control prefix costs were [1456,1328,0,1002] seconds, while the
remaining costs were [13492,13644,14944,13958]. Because all workers stop for
synchronous calibration replay, conservative makespan is max(prefix) plus
max(suffix), 16400 seconds, exceeding15300. The old package stays inert.

A new explicitly frozen public-cost task-rank plan keeps every task on the same
rank across both arms/repeats. Its independently recomputed prefix is
[894,1080,671,1141] and suffix [14010,14016,14009,14003]:15157 seconds,143 below
the15300 work allowance. This is a bounded planning fit, not a throughput
measurement or a global optimum. The input rank plan binds the exact challenges,
child costs and calibration task order. Both constructor and resource admission
recount the actual barrier; the default old LPT assignment remains rejected.

Interrupted final ledger tails and recognized JSON/UUID projection temporaries
are retained without qualification, with an explicit archive retention index.
Forbidden complete key tokens are checked even in incomplete/escaped JSON.
Unknown worker identities and non-lifecycle generation identities remain
forbidden. Mandatory control replay is repeated separately by the external
verifier without modifying committed export identity. Native-schedule input
and optional shared source-verification helper/prepare receipt are snapshot
bound. Host exclusive time may not exceed its inclusive phase, nullness must
agree, and fixed clock/overlap/unknown declarations are checked.

## Separate synthetic resource probe

`stage_nvarc_e10_probe.py` prepares an inert, independently pinned notebook for
four L4 workers. The unchanged native hardware gate requires four distinct
BF16 L4s; every worker loads the pinned SFT139 model and performs six cache
controls plus one reset control. The exact caps are 28 control forwards and
672 physical synthetic input tokens, zero optimizer steps, generations,
verification forwards or scientific task-runs. Its 1,800-second session includes
900 seconds startup, at most 600 seconds worker work and 300 seconds finalization,
with a two allocated-GPU-hour upper bound. This probe does not qualify TTT128
feasibility, real E10 quality or scientific continuation across sessions.

The exact `arc-prize-2026-arc-agi-2` competition attachment is needed for the
four-L4 resource shape, as recorded in Decision 0015 and the current rules
audit. It is resource entitlement only. Metadata and the immutable plan bind
that one source and the exact `/kaggle/input/competitions/arc-prize-2026-arc-agi-2`
directory. Runtime checks only directory metadata; it does not list its members
or open challenge/solution files. The synthetic probe scientific inputs stay
closed to its control tensors. `mount-policy.json` records that source-enforced
policy without claiming independent OS access attestation. Actual hardware,
quota, rules and source/license closure still require separate admission.
The same exact resource attachment is bound by the new development-screen
metadata/manifest. Its scientific payload remains the frozen public solver-
visible development challenges; no competition member is read in either path.

The first probe's missing competition attachment and the second probe's
completion/failure-lifecycle defects are retained under their original inert
identities. The repaired parent independently checks every assigned rank's
ready/result identity, complete hash-chained seven-forward/168-token ledger,
exact cache/position sequence, cache-vector comparison, reset inventory/prefill,
zero forbidden-work counters and finite host/CUDA memory observations. Worker
memory/stat failures preserve structured failure after completed controls.
Terminal disk failure downgrades the outcome, attempts a separately named
fallback receipt and still archives retained evidence after confirmed producer
stop. Stub-model CPU checks are engineering evidence only.

## Native notebook notice payload

The additive `irisx/native-code-material-contract-v2` keeps all v1 fields and
adds `notices_sha256`, the closed four-member map published by
`NOTICE_FILES_SHA256`. `read_materials` reads those exact files from
`materials/notices/`: the official Apache-2.0 license text, file-specific native
notice, modification/attribution guidance and audited provenance JSON. They are
payload/hash/manifest bound, repeated into each native subrun and preserved by
independent reconstruction. `material_files(contract)` exposes the exact
external slots to other builders. `native_notice_closure(contract, external)`
verifies their retained hashes. No extra arbitrary notice member is admitted.

The original three source-cell files remain byte-frozen. Newly rebound project
wrappers and generated native preparation prefix prominently attribute original
notebook portions and describe project modifications. The materialized helper's
new attribution header, if supplied, receives its own new material digest;
historical helper/source receipts remain unchanged.

V1 inputs stay valid for historical/inert preparation, but they carry no native
notice closure and cannot receive a new screen/probe runtime admission. V2
establishes only the specific source-notebook notice payload. The exact mounted
dependency/patch terms, full dependency inventory, model/data rights and current
provider/rules admission remain separate gates. `complete_dependency_license_closure`
stays false; the notebook author's Apache declaration does not license the whole
NVARC repository or independently authored project files.

The rendered probe/screen coordinator starts with only the unpacked project root
in `PYTHONPATH`, excluding the mounted dependency directory. The native preparer
first checks its selected inventory before explicitly inserting that directory
and importing Torch. This prevents that directory's `sitecustomize.py` from
running during the coordinator's Python startup. After preparation, native
workers retain their existing dependency path. This selected-entry gate does
not verify every mounted module/native binary, startup hook in the provider
image, current dependency notebook version or the full dependency license stack;
no complete pre-execution closure is claimed. Necessary execution permission and
independent provider/source gates remain outside the inert package.

The expanded all-task final CPU qualification retains the same 300-second hard
allowance per export, 300-second first-six calibration allowance, 1,500-second
finalization reserve and 18,000-second session. Its CPU duration is unmeasured.
The arithmetic planning fit does not establish that real replay fits these caps;
a timeout fails scientific qualification. No model workload, 96-task/140-test
denominator, scientific threshold or session/resource ceiling is enlarged.
