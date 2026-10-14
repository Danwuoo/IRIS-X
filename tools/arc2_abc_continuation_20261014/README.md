# Existing A/B/C: opt-in offline audit and sequential upstream loss

This package adds a training-audit reader interface and actual Agent Factory 3
sequential loss reduction beside the existing A/B/C experiment. It does not
start a model, optimizer, collector, scorer, provider call or local-executor task.
For mutable development status and acceptance evidence, use the single
[development progress document](../../research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md).
This README describes interfaces and operational limits, not another progress list.

## Inputs: original audit bytes, not a compact terminal report

The input is one explicitly supplied original `experiment/audit/sweep-N.json`
from the existing producer. It contains `batch`, `summary`, `update`, status,
batch order and before/after policy declarations. The compact
`TERMINAL-VALIDATION.json` lacks original trajectories and cannot substitute.
Use the existing Stage 0 `analyze` interface for that compact A/B/C report;
this package adds a different, per-training-batch check.

The second input is a deliberately supplied context document with the closed
`irisx/abc-audit-context-v1` schema. It binds the audit's exact SHA256 and the
caller-declared training/policy context. Obtain declarations from the original
independently retained training panel, exclusion, source and policy receipts.
Missing artifacts remain missing: do not reconstruct them from PUBLIC results,
the compact report, guessed defaults or the synthetic tests.

| Top-level field | Required content |
| --- | --- |
| `format` | `irisx/abc-audit-context-v1` |
| `audit_sha256` | SHA256 of the original complete audit file, including its serialization |
| `batch_context` | All fields of the existing `BatchContext`, using JSON lists for its tuple fields: ordered train32 parents/records, complete exclusion declarations, batch index0–3, policy version, actor identity, generation epoch, panel and sampling-policy hashes, explicit evidence kind |
| `training` | `source_sha256`, `manifest_sha256`, `plan_sha256`, `exclusions_sha256`, and32 ordered `record_declarations` |
| each record declaration | `parent_id`, `record_id`, `messages_sha256`, `target_sha256`, `exclusion` |
| `policy_before` | `policy_version`, `adapter_sha256`, `source_sha256`, `generation_epoch` |

Public implementation files and the native sampling-policy bytes are checked
against the pinned source manifest. The caller's training, policy and actor
source identities remain declarations, not authenticated execution evidence.
A context hash only binds that document's bytes; it does
not authenticate its author, prove the truth of its reward/lineage declarations,
or replace original owner/release admission. No evaluator answer is needed or
accepted as a way to fill missing context. Do not publish real training receipts,
raw tokens, original artifacts or account material with this source package.

## CLI

From the repository root, using an already prepared CPU environment with the
dependencies recorded by the [existing bridge](../arc2_agent_factory3_bridge_20261014/README.md):

```sh
python -B -m tools.arc2_abc_continuation_20261014.cli \
  --audit ORIGINAL_LOCAL_AUDIT.json \
  --audit-sha256 SHA256_OF_ORIGINAL_AUDIT_BYTES \
  --context ORIGINAL_LOCAL_CONTEXT.json \
  --context-sha256 SHA256_OF_CONTEXT_BYTES \
  --output NEW_LOCAL_REPORT.json
```

The capitalized paths/hashes are placeholders. Output parents must already
exist, and the output filename must be new. There is no directory search,
automatic artifact download, path-following from input JSON, or overwrite mode.
The old Stage 0 prepare/analyze commands remain standard-library-only; this
new optional CLI imports tensor dependencies only after input file checks.
`--help` needs no tensor packages. No dependency installer runs from this CLI.

Both files use the existing descriptor-relative no-follow reader unchanged:
regular single-link files, exact hashes, strict JSON, and **16MiB per file**.
The producer's derived per-batch audit upper bound is approximately88MiB. An
actual file above16MiB is explicitly unsupported here and is rejected before
analysis. Do not truncate/split a batch, suppress slots, or increase the old
reader's limit to make it fit. Larger-file support remains a separately reviewed
bounded-reader implementation, not an implied capability of this release.

Exit/status interpretation:

- `OFFLINE_AUDIT_OUTPUT_WRITTEN` / exit0 means a new report was written. Inspect
  its `status`, `conformance_complete`, `issues`, coverage and nullable replay
  results; a written report may explicitly say incomplete, rejected or unknown.
- `CONFORMANT_SAVED_REPLAY` checks saved declarations, original-token scalar
  replay values and recorded loss against actual upstream CPU computation.
  `CONFORMANT_ZERO_SIGNAL` means a complete constant-reward batch needs no replay.
- `MISSING_ORIGINAL_ARTIFACTS`, `INCOMPLETE_AUDIT`, `NOT_REACHED`,
  `FATAL_NATIVE_STATE`, `NUMERIC_NONADMISSION`, `UPDATE_FAILED` and `REJECTED`
  remain separate. Neither missing work nor a failed audit becomes reward0.
- `INPUT_REJECTED` / exit2 covers arguments, files, hashes, context parsing and
  safe output failures; `DEPENDENCY_UNAVAILABLE` / exit3 identifies missing
  optional CPU packages without printing private import paths.
- Cooperative SIGINT/SIGTERM returns `INTERRUPTED` / exit130. The calling process
  must still enforce its timeout and wait for actual exit. The original safe-I/O
  [handoff limitations](../../research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#4-檔案安全與中斷後續接)
  apply: after exclusive publication a complete file may remain on later failure;
  inspect it before retrying. SIGKILL/power loss cannot guarantee Python cleanup.

Outputs omit original identifiers, prompts, tokens, grids, probability arrays
and private source errors. Hash/shape/numerical consistency never enables
`provenance_authenticated`, `model_replay_verified`, `model_gradients_verified`,
`physical_execution_verified`, `production_update_authorized` or
`ABC_efficacy_established`.

## In-memory APIs and model-owner boundary

- `audit.context_from_document(doc, audit_sha256=...)` creates the explicit
  declared context. Its caller must independently check the original file bytes.
- `audit.analyze_audit(audit, context, leaf_logp_derivative=False)` returns a
  compact per-batch report. Optional derivatives use fresh CPU logp leaves;
  they cannot reconstruct original logits, model graphs or LoRA gradients.
- `streaming.StreamingLossSession(prepared)` snapshots a complete validated
 64-slot `PreparedBatch`; it does not regroup individual trajectories.
  `contribute(sample_id, CPU_logp)` requires exact original order and returns
  one actual upstream differentiable micro-contribution. Consume and release
  that contribution before supplying the next replay graph. `finalize()` only
  succeeds after the required whole batch, or on the explicit zero-signal path.
  `abort()`/context-manager exit clear incomplete detached session state.

Each contribution retains the original group-centered advantage and full-batch
`M×8×T_i` divisor. The original full-batch padding width is retained for upstream
float32 metric reductions. The session retains declaration snapshots and
detached metric accumulators, not the caller's replay tensors or graphs.
The caller can still retain returned graphs; this interface cannot prevent that.
Already accumulated caller gradients are not rolled back by `abort()`.

There is no optimizer/commit API. Returning a micro-loss before finalization
does not authorize an update. A real local owner successor must preserve
one-graph-at-a-time replay/backward, all original replay/gradient/state gates,
rollback, save/reload, closure and physical cost accounting. Shadow work is
charged to its own declared version; if included in B, the whole extra B wall
must be matched by C. Existing SFT256, fixed disjoint batches, noTTT and
PUBLIC120 tasks/167 queries remain the scientific experiment.

## Local shadow wiring specification

This is an inert integration specification for a separately reviewed local
successor. The current implementation accepts CPU tensors only; it is not a
CUDA model hook. Do not copy real model tensors to CPU and call that production
integration or reuse the frozen owner's old admission for changed code.
The exact inspected public files are listed in
[audit-source-pins.json](audit-source-pins.json).

| Original producer evidence | Adapter projection | Local owner's remaining responsibility |
| --- | --- | --- |
| `flow.py` sweep `batch`, index, parents, rows and `summary` | Original order, complete8×8 slots, declared train32/exclusions, recomputed group summaries | Authenticate original records/panel/exclusions; never invent slots from terminal summaries |
| `actor.py` original prompt/generated IDs, prefix positions, DFA states/support, behavior logp, version/epoch/cache and event declarations | Native trajectory validation and unchanged `PreparedBatch`/`TrainingSample` mapping | Verify the actual tokenizer/model/adapter bytes, causal alignment, cache disposal and physical owner events |
| `runtime.py` `update.replays[]`, original lengths and recorded detached loss | Saved-scalar checks plus actual upstream `StreamingLossSession` micro-contributions | Obtain real differentiable replay tensors from the unchanged policy; validate each LoRA target gradient |
| `runtime.py`/`ledger.py` numeric gate, commit/rollback, budgets and closure | Preserve reported state distinctions; no optimizer or admission authority | Keep all gates before commit, restore on any failure, verify save/reload and owner exit; charge all physical work |

Local comparison procedure, only after the receiver's original material and
execution admission is satisfied:

1. Bind a new successor source identity, the same saved SFT256 anchor A and one
   original complete training-only batch. Preserve the original batch index,
   raw tokens, policy/adapter version, epoch, support and rewards. Record their
   independent provenance and hashes. A later B batch must use its own exact
   declared pre-update policy descended from A, not a fresh reload of A.
2. Snapshot that identical pre-update owner state and clear gradients. Run the
   frozen reference replay/backward one trajectory at a time, collecting loss
   and detached per-LoRA-target gradients. Do not step the optimizer. Check
   model bytes/state are unchanged; restore the snapshot and clear gradients
   before the comparison path, keeping the physical work in the ledger.
3. On the same unchanged policy and complete batch, use the separately reviewed
   model-compatible successor to obtain the real replay graph and apply the
   actual upstream micro-loss with the full-batch `M×8×T_i` normalization.
   Backward and release each graph before the next. Compare loss and every
   named LoRA target's shape, finite values, norm and numerical difference to
   the reference under the receiver's predeclared dtype-specific tolerances.
   CPU saved-logp derivatives cannot satisfy this step. M=0 stays no-replay/
   no-update; zero-advantage rows in mixed batches retain replay diagnostics.
4. Retain the original nonforced max-gap≤0.20, p95≤0.05 and unclipped fraction=1
   gates, finite per-target gradients and at least one nonzero target. No
   update may occur before the full batch passes. Exercise real failure
   rollback, unchanged pre-commit weights, save/reload and complete process
   closure independently; neither `finalize()` nor an output file authorizes
   commit. Preserve failed work, clocks and costs when rejecting a comparison.
5. Account for forward/backward, transfer, synchronization, hashing, Python,
   peak allocated/reserved memory, saving and failure/cleanup wall. A separate
   shadow diagnostic has its own source/cost identity. If admitted into B,
   match C to the entire extra B model-phase wall from the same A, not just
   optimizer time. Keep the original whole-session12h and operation/batch
   deadlines, selection rule, noTTT and sealed PUBLIC120/167 denominator.

Missing real audit/provenance, files above16MiB, a CPU-only interface or absent
model-compatible successor remains an explicit local prerequisite. No command
in this specification launches the model or dispatches an update.

## Reproduce focused tests

```sh
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 python -B -m unittest discover -s tools/arc2_abc_continuation_20261014/tests -v
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 python -B -O -m unittest discover -s tools/arc2_abc_continuation_20261014/tests -v
```

Fixtures are fabricated, non-ARC, producer-shaped records. Source interoperability
checks compare the original producer/consumer functions; they are not historical
model execution. Synthetic raw-logit differential tests are likewise not GPU
memory, real unchanged-model replay or ARC improvement evidence. Current test
results and limitations belong only in the linked progress/review records.
