# Phase 6 Direct Pressure Sampling

- **ID:** `note-2026-09-08-phase-6-direct-pressure-sampling`
- **Status:** result — **Result C — Sampling not semantically interpretable**
- **Scope:** Phase 6 Batch 2 TURN B collection and interpretation of the single
  TURN A launch. No task was rerun and no model/provider call was made in TURN B.
- **Definition/code freeze:** `ba7ef9964d268d1342d7cec02beedd5563c0136a`
- **Launch-ready SHA:** `cacdb53105f8b2d378e618d8ac785eac4501c1c1`
- **Raw collection evidence commit:** `3e240434a72b9fe48d0456ad039d91048169a5d4`
- **Adjudication evidence commit:** `7340167a466ce013a96bf2b0cb1834cca73ed863`

## Question and governing authority

The Batch 2 question was whether one unchanged admitted cheaper allocation
would expose real task-level semantic pressure across six frozen tasks, and
whether any direct trigger predicate could be bound deterministically to an
immutable observation. The controlling plan is
`docs/plans/TEMP_PHASE_6_MECHANISM_FREE_DIRECT_PRESSURE_SAMPLING.md`.

The source-stated discipline inherited from Phase 5 and Phase 6 Batch 1 is:

```text
observation != attribution
attribution != intervention
intervention != trigger
semantic miss != retry or escalation evidence
task heterogeneity != routing evidence
```

The exact admitted allocation was Codex CLI 0.147.0, provider slot
`irisx_openai_no_retry`, GPT-5.6 Luna, medium reasoning, ChatGPT
authentication, read-only sandbox, approval never, disabled model tools, and
zero retry, route, fallback, escalation, or recovery actions.

## Directly observed collection state

The single TURN B process inspection found PID `16592` inactive and the exact
recorded staging root present. `batch-completion.json` records that the original
runner attempted P1 through P4 in fixed order and stopped on a systemic or
safety failure. P5 and P6 were not attempted.

Every available staging file was hashed before collection and preserved
byte-for-byte. The immutable inventory is
`experiments/phase-6-pressure-sampling-v0/runs/batch-2/staging-inventory.json`.
The frozen collector failed closed because P4 had no `raw-output.txt`; no file
was created to fill that absence. The available evidence was then preserved
without normalization or repair, including the empty runner stdout/stderr
files and the explicit absence record.

The definition/code surface is byte-identical between the freeze and
launch-ready commits. The only post-freeze paths before launch were the
admission record and launch manifest. All four attempt commands normalize to
the admitted profile. No model, reasoning-effort, provider-slot, retry,
fallback, route, escalation, recovery, tool, authentication, or sandbox drift
was observed.

## Per-task observations and attribution chain

| Task | Execution and result | Raw observation → shortfall → stage → attribution → candidate intervention → predicate → decision |
| --- | --- | --- |
| `phase6-p1-multi-constraint-selection-v0` | Attempted; one invocation boundary; usable structured result; exact deterministic oracle match; `verified_success`. | Exact output and terminal hashes → no shortfall → not applicable → not attributable → none → no positive pressure predicate → retain only bounded task success. |
| `phase6-p2-multi-group-exact-aggregation-v0` | Attempted; one invocation boundary; usable structured result; exact deterministic oracle match; `verified_success`. | Exact output and terminal hashes → no shortfall → not applicable → not attributable → none → no positive pressure predicate → retain only bounded task success. |
| `phase6-p3-constrained-multikey-ranking-v0` | Attempted; one invocation boundary; usable structured result; exact deterministic oracle match; `verified_success`. | Exact output and terminal hashes → no shortfall → not applicable → not attributable → none → no positive pressure predicate → retain only bounded task success. |
| `phase6-p4-dependency-closure-v0` | Attempted; one invocation boundary; provider process failed; no raw model result; semantic verification not assessed; `systemic_failure`. | Provider event states that response-format schema field `uniqueItems` is not permitted → evidence/sampling-path shortfall → `systemic_execution_failure` → directly supported at that boundary, not model-intrinsic → separately authorized non-semantic sampling-path repair → task-pressure predicate unsupported/unknown → exclude from capability inference. |
| `phase6-p5-deterministic-record-reconciliation-v0` | Not attempted after the mandatory systemic stop; zero calls; `incomplete_not_attempted`. | Batch completion omits a P5 attempt → missing task evidence → `unknown` → not attributable → no TURN B intervention → predicates unknown/unsupported → no capability inference. |
| `phase6-p6-ordered-rule-precedence-v0` | Not attempted after the mandatory systemic stop; zero calls; `incomplete_not_attempted`. | Batch completion omits a P6 attempt → missing task evidence → `unknown` → not attributable → no TURN B intervention → predicates unknown/unsupported → no capability inference. |

The P4 failure is not a semantic miss. It does not establish an intrinsic model
capability failure, retry benefit, stronger-allocation benefit, routing benefit,
workflow benefit, or a capability-pressure event. The P5/P6 absences are the
required consequence of the frozen stop policy, not task failures.

## Derived assessment

The frozen summary deterministically records:

```text
authorized tasks: 6
attempted tasks: 4
verified successes: 3
semantic misses: 0
systemic failures: 1
unresolved / unattempted: 2
logical model-call boundaries crossed: 4
retries / routes / fallbacks / escalations / recovery / tools: 0 / 0 / 0 / 0 / 0 / 0
```

The direct-predicate artifact contains 12 provenance-bound records: 1 `true`,
7 `false`, 4 `unknown`, and 0 `conflicting`. Every resolved record binds the
frozen derivation rule, source path, source SHA-256, JSON pointer, and observed
value. The four unknown records remain unknown because the original run did
not produce the required task or comparison observations. No manual Boolean
was introduced.

| Capability family | Derived direct-evidence status | Interpretation |
| --- | --- | --- |
| H-G1 automated specialization | `not_triggered` | Task authoring remained manual and frozen. |
| H-W1 workflow machinery/search | `not_triggered` | The sample used one fixed control flow; no workflow alternative was evaluated. |
| H-C1 cascade/escalation | `insufficient_or_ambiguous` | No valid semantic miss was established for the complete sample, and no stronger candidate or trade-off was observed. |
| H-R1 feature-based routing/allocation | `not_triggered` | Feature heterogeneity is true, but allocation count is one and no frontier change was compared. |
| Runtime persistence | `not_triggered` | No state-continuity requirement existed. |
| Nondeterministic verifier/model judge | `not_triggered` | Deterministic oracles remained the declared authority; P4 was not an oracle insufficiency. |
| External action/interception expansion | `not_triggered` | The sample required no external or irreversible action. |
| General recovery/retry | `insufficient_or_ambiguous` | No retry/recovery comparison or independently observed benefit exists. |

No capability gate changed to `triggered_by_direct_evidence`. The two
`insufficient_or_ambiguous` statuses are not positive triggers and are not
silently rewritten as negative evidence. No negative-control fact acted as an
unconditional veto.

## Resource observations

Four logical model-invocation boundaries were crossed against the ceiling of
six; three produced completed usable model results. P1–P3 directly report
15,235 input tokens, 643 output tokens, and 408 reasoning tokens in total. P4
token usage is `Unknown`, so complete batch token totals are `Unknown` rather
than the partial sum. Summed observed runner wall time is 24,759,044,700 ns.
Network calls, transport request count, and provider cost are `Unknown`.
Paid API calls are recorded as zero under ChatGPT subscription execution; no
API-price inference is made.

## Result classification

**Result C — Sampling not semantically interpretable.**

The six-task semantic sample did not complete authoritatively: P4 failed before
a usable result because the frozen response schema was rejected, and the
correct systemic stop left P5/P6 unattempted. The required evidence gap also
caused the frozen collector to reject the incomplete P4 artifact set. This is
not Result D because collected source hashes, freeze identity, admission
identity, derivation-rule authority, and negative-control semantics are
consistent; no provenance contradiction was found.

The three completed successes remain valid task-local observations. They do not
make the intended six-task sample semantically interpretable and do not support
a population or general-capability conclusion.

## Supported conclusions

- The frozen allocation produced exact verified success on P1, P2, and P3.
- The original runner honored fixed ordering and stopped after the P4 systemic
  failure without retrying or consuming P5/P6 calls.
- P4 exposes a non-semantic response-schema compatibility gap in the sampling
  path under the exact frozen execution surface.
- Direct predicate provenance regenerated byte-identically and no capability
  gate was triggered.
- Historical Phase 4/5 evidence, Phase 6 Batch 1 evidence, `sources/`,
  `references/papers/`, and `irisx/core/` remain unchanged.

## Unsupported conclusions, ambiguities, and unknowns

Not established: P4/P5/P6 task capability, model-intrinsic causal failure,
retry benefit, stronger-allocation benefit, routing benefit, workflow benefit,
generalization beyond the three completed tasks, long-term reliability,
lifecycle-cost superiority, provider portability, production readiness, final
failure ontology, or final architecture.

Unknown: complete token usage, network/transport counts, provider cost, whether
P4 reached model inference beyond the logical invocation boundary, and the
semantic outcomes P4–P6 would have produced under a valid sampling path.

Conflicting evidence: none. The evidence is incomplete, not contradictory.

## Exact next recommendation

Under a separate owner-authorized scope, repair and requalify only the
non-semantic sampling path: add deterministic provider-response-schema
admissibility coverage and make missing-output systemic evidence collectable
without fabricating a raw result. Do not infer a capability mechanism, do not
reuse unused Batch 2 allowance, and do not rerun this batch. Phase 6 Batch 3 is
not started or authorized by this result.
