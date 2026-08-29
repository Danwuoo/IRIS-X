# Phase 4 Scoped Mechanism-Experiment Results

- **ID:** `note-2026-08-30-phase-4-mechanism-results`
- **Status:** result — reviewed scoped batch
- **Question/scope:** Record separate results for H-M1a, H-V1a, and H-O1a
  on `taskdist-2026-08-28-vanta-docops-readonly-12`. This note does not rank
  mechanisms, synthesize architecture, authorize another experiment, or begin
  Phase 5.
- **Corpus records:** `src.spex`, `src.vanta`,
  `src.nemo-agent-toolkit-develop`

## Evidence Basis

| Evidence | Classification | Use in this batch |
| --- | --- | --- |
| `src.spex`: `sources/predecessors/spex/docs/eval/ARC-AGI-1-Run-Artifact-Substrate-v0.md`, `ARC-AGI-1-G0-S1-Development-v0.md`, and `src/spex_arc/runner/arc_a1.py` | Source-stated and directly observed imported mechanism evidence | Motivated frozen identity, fail-closed mismatch handling, terminal records, and separately derived aggregates. SPEX's ARC types and architecture were not inherited. |
| `src.vanta`: `sources/predecessors/vanta/docs/02_specs/Evidence_Packet_and_Verifier_Runtime.md`, `Commit_Abort_Replay_Semantics.md`, `Failure_Taxonomy_v0.md`, and `docs/04_experiments/Experiment_002_Evidence_Verifier.md` | Source-stated imported mechanism and limitation evidence | Motivated independent verifier decisions and separate false-accept/false-reject accounting. VANTA results were not treated as IRIS-X results. |
| `src.nemo-agent-toolkit-develop`: `sources/external/NeMo-Agent-Toolkit-develop/docs/source/improve-workflows/profiler.md`, `evaluate.md`, and `packages/nvidia_nat_core/src/nat/data_models/profiler.py` | Source-stated and directly observed imported instrumentation evidence | Motivated per-invocation timing/usage and separate profile artifacts. NeMo Agent Toolkit was not adopted as a dependency. |
| The three completed run directories named below | Directly observed local experiment evidence | Supplies raw terminal/profile records, immutable run manifests, derived aggregates, and reviewed interpretations. |

All three runs asserted the active registered VANTA snapshot tree
`4e095233520418705168f40a556177477839b052`, used no network/model/paid
service, and left imported source clean.

## H-M1a — Registered Source Snapshot Assertion

**Exact hypothesis**

> Resolving a run's `source_id` and `source_snapshot_id` through
> `corpus/sources.yaml` and asserting that the observed Git source-tree OID
> equals the registered snapshot tree OID will detect deliberately injected
> source-identity mismatches that a record-only provenance path does not
> detect, while accepting the valid registered identity.

- **Experiment ID:** `exp-2026-08-30-source-snapshot-assertion`
- **Completed run ID:** `hm1a-20260830-local-01`
- **Evidence classification:** directly observed local deterministic
  synthetic-challenge evidence; task-local harness integrity
- **Support status:** `Supported — task-local`
- **Actual observed result:** 30/30 valid terminal records. Treatment accepted
  the valid identity 3/3, rejected four mismatch types 12/12, and produced zero
  false accepts/rejects. Record-only accepted those 12 mismatches. All ten
  arm/case pairs agreed over three repetitions.
- **Reliability observation:** deterministic decision repeat agreement under
  the declared horizon; long-term, robustness, stateful, change, and recovery
  reliability were `Not evaluated`.
- **Cost observation:** treatment read 421,935 registry bytes, performed six
  Git tree lookups, and recorded 342.583 ms wall / 46.875 ms process CPU across
  15 records. Timing comparison is descriptive because arms take different
  early-exit paths.
- **Remaining uncertainty:** upstream provenance is `Unknown`; complete H-M1,
  non-source manifest mismatch detection, and cost at broader scale are
  `Not established`.
- **Narrow supported constraint:** evidence-producing paths in this scoped
  batch should fail closed before episodes unless source ID, active snapshot
  relationship, and Git source tree at the code commit resolve and match.

This does not establish the parent manifest/terminal-record/resource-ledger
hypothesis or an architectural invariant.

## H-V1a — Independent Acceptance Verification

**Exact hypothesis**

> Holding producer output, system claim, task bytes, evidence/path-hash
> substrate, and actual-outcome adjudication fixed, requiring an independent
> deterministic verification decision before accepting a claimed success will
> reduce false-success acceptance relative to claim-only acceptance on frozen
> invalid-output challenges, without rejecting semantically valid
> claimed-success outputs in the evaluated finite sample.

- **Experiment ID:** `exp-2026-08-30-docops-acceptance-verification`
- **Completed run ID:** `hv1a-20260830-local-01`
- **Evidence classification:** directly observed finite-sample, oracle-backed,
  paired acceptance-policy evidence
- **Support status:** `Supported — task-local`
- **Actual observed result:** 360/360 valid terminal records. Claim-only
  recorded 72 true accepts and 108 false accepts. Independent verification
  recorded 72 true accepts, 108 true rejects, zero false accepts, and zero
  false rejects. All 36 canonical and 36 semantic-equivalent treatment records
  were accepted; all 108 invalid treatment records were rejected. Paired
  actual outcomes and fixed fields were identical.
- **Reliability observation:** decisions repeated across three repetitions with
  zero verifier errors; this is deterministic operational repeatability, not
  general verifier reliability.
- **Cost observation:** treatment verification recorded 101.2129 ms wall and
  140.625 ms process CPU across 180 records. Producer output was 25,887 bytes
  per arm; decision artifacts were 23,220 bytes control and 23,364 bytes
  treatment; combined raw terminals were 772,639 bytes.
- **Remaining uncertainty:** held-out and real-workload behavior, model judging,
  oracle validity beyond fixture bytes, and production evidence sufficiency are
  `Not established`.
- **Narrow supported constraint:** for these frozen oracle-backed outputs,
  claimed-success acceptance should depend on an independently computed
  semantic verifier decision rather than the claim alone.

The observed 0/108 false accepts is an exact finite-sample result, not evidence
of perfect verifier reliability.

`H-V1b — evidence/provenance binding: deferred / not evaluated in this batch`

## H-O1a — Structured Instrumentation Completeness

**Exact hypothesis**

> Holding task, control behavior, evaluator, resource envelope, and execution
> policy fixed, structured profiling will reduce missingness for a predeclared
> runtime-profile field set while preserving paired output and actual-outcome
> behavior. Artifact-size and timing overhead must be measured descriptively
> rather than assumed.

- **Experiment ID:** `exp-2026-08-30-docops-profile-instrumentation`
- **Completed run ID:** `ho1a-20260830-local-01`
- **Evidence classification:** directly observed paired deterministic
  instrumentation evidence under a predeclared 17-field contract
- **Support status:** `Supported — task-local`
- **Actual observed result:** 72/72 valid episodes. Coverage increased from
  0/612 to 612/612 required field instances. All 36 paired output hashes,
  actual outcomes, terminal statuses, evidence states, and post-input snapshots
  matched; both arms had 36/36 task successes and zero profiler errors.
- **Reliability observation:** all task/arm results agreed over three
  repetitions and instrumentation introduced no invalid episode. Broader
  observability and long-term reliability are `Not evaluated`.
- **Cost observation:** structured profiles occupied 28,023 artifact bytes;
  canonical profile payloads totaled 26,295 bytes. Terminal-record payloads
  were 100,167 bytes off and 113,063 bytes on. Mean paired wall delta was
  0.0924917 ms with 21 positive and 15 negative pairs.
- **Remaining uncertainty:** `Timing overhead magnitude/direction: Not
  established under this horizon.` Sufficiency of this field contract for
  model/tool/stateful workflows is `Unclear`; production performance and
  storage cost are `Not established`.
- **Narrow supported constraint:** the frozen task-relevant profile can be
  captured completely around this deterministic control without changing its
  paired task result, at an explicit artifact-size trade-off.

This does not make structured profiling or this field set an IRIS-X
architectural invariant.

## Cross-Result Boundary and Uncertainty

No winner ranking or scalar success–reliability–cost score is produced. The
results test distinct mechanisms and cost vectors.

- **Unknown:** upstream revisions/provenance beyond registered local trees;
  electricity, hardware depreciation, development/maintenance effort,
  fixture-authoring effort, and external failure impact.
- **Unclear:** whether the H-O1a field set is sufficient for future model,
  tool, stateful, or long-running executions.
- **Not established:** held-out/general performance, deployment thresholds,
  stable timing overhead, complete lifecycle cost, parent H-M1/H-V1/H-O1, and
  any final architecture.
- **Not evaluated:** H-V1b, H-I1, H-P1, H-G1, H-W1, H-C1, H-R1, model-based
  mechanisms, paid APIs, stateful reliability, robustness, change reliability,
  recovery reliability, additional Phase 4 mechanisms, and Phase 5 synthesis.
- **Invalid runs:** none in this Phase 4 batch.

## Closure

The three-experiment batch is complete. Retirement of its temporary plan means
only that this scoped evidence batch finished. It does not authorize a fourth
mechanism, final architecture synthesis, or Phase 5.
