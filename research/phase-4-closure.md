# Phase 4 Closure

- **ID:** `note-2026-09-03-phase-4-closure`
- **Status:** result / closure decision
- **Question/scope:** Synthesize the accumulated Phase 3 and Phase 4 evidence through H-P1a and decide whether Phase 4 is complete. This document does not select, design, or implement an architecture and does not begin Phase 5.
- **Primary new result:** `H-P1a — Supported — task-local`

## Evidence basis and classification

| Evidence | Classification | Closure use |
| --- | --- | --- |
| `experiments/exp-2026-08-28-docops-readonly-baseline/runs/pilot-20260828-local-rerun-01/` | Directly observed local Phase 3 development evidence | Establishes the initial outcome/evidence/resource substrate and a task-local structured-handler gain over a narrower literal control. |
| `research/phase-4-mechanism-experiment-results.md` | Reviewed directly observed Phase 4 evidence | Supplies H-M1a, H-V1a, and H-O1a results and their finite-sample boundaries. |
| `research/phase-4-evidence-interception-results.md` | Reviewed directly observed Phase 4 evidence | Supplies H-V1b and H-I1a results and their finite-sample boundaries. |
| `research/phase-4-reliability-specialization-readiness.md` | Reviewed directly observed Phase 4 evidence and prior decision | Supplies H-OR1a, H-SR1a, H-RCV1a, substrate qualifications, and the earlier readiness-to-design-H-P1 decision. Its then-future statements are preserved as historical state. |
| `experiments/exp-2026-09-01-luna-structured-program-specialization/design/design-20260902-chatgpt-03/` and `runs/blind-20260902-chatgpt-03/` | Directly observed model-backed, post-freeze generated-blind evidence | Supplies the valid H-P1a design, selection, blind results, resource ledgers, and bounded Terra reference. |
| This synthesis and closure decision | Inference constrained by the reviewed records above | Determines only that the Phase 4 evidence program is complete enough to hand off to a separately authorized architecture-synthesis phase. |

Imported projects remain evidence and reference material. No predecessor or external framework is adopted here as IRIS-X architecture.

## Accumulated evidence

### Supported task-local constraints

The following are narrow constraints supported under their frozen local contracts, not universal architecture requirements:

- **Registered identity before evidence production — H-M1a.** Source ID, registered snapshot relationship, and observed Git tree must resolve and match for the scoped evidence-producing path to proceed. The treatment detected all 12 injected mismatch cases over three repetitions and accepted the valid identity.
- **Independent acceptance verification — H-V1a.** Claimed success should not become accepted success solely from the producer claim when an independent deterministic semantic verifier is available. The scoped treatment rejected all 108 invalid claimed-success records with zero false rejects in its valid-equivalent cases.
- **Evidence/path-hash binding — H-V1b.** Semantically correct output alone did not justify verified-success eligibility when required evidence was missing, stale, crossed, unrelated, or conflicting. All 252 invalid/insufficient treatment records were denied eligibility while their actual outcomes remained success.
- **Pre-execution prevention — H-I1a.** When prevention is required, policy evaluation must precede the mutation primitive and the prevention claim must be checked against measured post-state. The treatment prevented all 18 scoped prohibited mutations and allowed all six controls.
- **Explicit structured instrumentation — H-O1a.** The declared 17-field profile was captured for all 612 field instances without changing paired deterministic task outcomes, at a measured artifact-size trade-off.
- **Targeted recovery — H-RCV1a.** On five frozen deterministic failure states, exactly one declared recovery action restored all 15 treatment episodes to independently verified valid state; detect-only restored none.
- **Structured-program specialization — H-P1a.** At fixed Luna runtime and all other declared factors, optimizer-generated C1 achieved 32/32 blind verified successes versus C0's 18/32, with 14 paired wins, zero paired losses, and false success reduced from 14 to zero. The exact result is `Supported — task-local`.

The Phase 3 development pilot also directly observed 36/36 success for the structured deterministic control versus 21/36 for the narrower literal control. This contradicted H-B0 and observed H-B1 only for the enumerated development fixtures and declared repertoire difference; it did not select an architecture.

### Stable-under-horizon reliability observations

- The Phase 3 corrected pilot completed 72/72 episodes with zero invalid episodes and full same-environment repeat agreement across three repetitions.
- H-OR1a observed 480/480 successful episodes, zero sequence-position drift, and no fresh/long-lived mismatch across 12 tasks, 20 fixed-order passes, and two process-lifetime arms.
- H-SR1a observed exact baseline restoration in all 120 reversible-cycle records, with zero residual path or byte drift across fresh and persistent workspace arms.
- H-RCV1a's detection and recovery decisions repeated over three repetitions without invalid episodes or recovery-induced side effects.
- The deterministic H-M1a, H-V1a, H-V1b, H-I1a, and H-O1a decisions repeated under their declared local horizons.

These are stable-under-declared-horizon observations. They do not establish days/weeks operation, stochastic model stability, crash/restart continuity, concurrent or multi-host behavior, or production reliability.

### Rejected or mixed mechanisms

- Phase 3 H-B0 was contradicted on the development fixtures: the declared repertoire difference changed five distinct tasks over three repetitions.
- No scoped Phase 4 sub-hypothesis completed with a `Mixed evidence` or rejected task-local label. That absence is not evidence that the untested parent mechanisms or alternative treatments would succeed.
- H-P1a was supported, but the parent H-P1 remains unresolved because complete lifecycle-cost offset, broader/repeated optimization behavior, and general task-distribution performance were not established.

No cross-mechanism winner ranking or synthetic success–reliability–cost scalar is inferred.

### Qualified reusable substrate

The following are qualified for later use within their documented limits:

- evaluation-state semantics that keep actual outcome, evidence status, acceptance, verified-success eligibility, and execution state separate;
- frozen manifests, terminal records, output freezes, raw reconstruction, and distinct design/runtime resource ledgers;
- the 48-fixture Document Ops task frame with 21 local, 14 copied-workspace, 7 substrate-only, and 6 framework-dependent/deferred fixtures;
- dimension-specific operational, stateful, robustness, change, and recovery protocols without a unified reliability scalar;
- deterministic robustness perturbation and change-regression measurement substrates, which establish measurement sensitivity rather than system robustness or maintainability;
- held-out governance with candidate freeze, post-freeze blind generation, no cherry-picking, and output freeze before evaluation;
- the four generated families: traceability extraction, terminology consistency, path/action guard, and structured simulation;
- the corrected specialization execution contract, canonical failure semantics, fake-candidate qualification, family-specific provider schemas, and zero-call provider-schema preflight.

These are reusable research/evaluation substrate, not a final runtime, ontology, framework dependency, or architecture.

## H-P1a and bounded Terra reference

The valid design run `design-20260902-chatgpt-03` used six optimizer-generated, byte-unique candidates. Frozen validation selected `opt-02-r01`, SHA-256 `8bf10ea83da6c6096405d1c12a045c9830f5d4a6dc2ebefeff538a9fc5eeec1b`, 2,764 bytes, at 16/16 validation verified success; the 1,389-byte seed achieved 10/16. The candidate-freeze commit `6ef4c9d09e6124a9cb6c47f6b12427be29dea19e` predates blind-seed generation.

The blind inventory contained 32 valid tasks, eight per family, and the interleaved schedule contained 96 exactly-once entries. C1 achieved 8/8 in every family. C0 achieved 8/8 traceability, 6/8 terminology, 4/8 path/action guard, and 0/8 structured simulation. All 96 calls completed with sufficient evidence and no malformed output, invalid binding, subscription event, provider terminal failure, tool attempt, retry, recovery, route, or escalation.

C2 was Terra with the exact C0 seed bytes and SHA. C1 was no worse than C2 on the frozen strict reference dimensions and achieved 32/32 versus C2's 23/32 verified successes. The permitted conclusion is `Observed finite-sample runtime-capability substitution — task-local`. This is not Luna/Terra equivalence, not a general capability claim, and not a second H-P1 treatment.

## Resource and monetary boundary

Design-time and blind runtime remain separate:

| Ledger | Luna calls | Terra calls | Total calls | Input tokens | Cached input tokens | Output tokens | Reasoning tokens | Wall time ns |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Design | 280 | 6 | 286 | 4,662,788 | 2,071,808 | 46,319 | `Unknown` | 3,252,150,852,300 |
| Blind runtime | 64 | 32 | 96 | 1,568,774 | 446,464 | 15,015 | `Unknown` | 899,036,687,900 |
| Combined resource observation | 344 | 38 | 382 | 6,231,562 | 2,518,272 | 61,334 | `Unknown` | 4,151,187,540,200 |

The attempt exactly reached, but did not exceed, the independent 344 Luna / 38 Terra / 382 total call ceiling. Token and time fields are observed resource vectors. They are not actual ChatGPT subscription-dollar cost.

`provider_cost_usd: Unknown`

`monetary lifecycle-cost advantage: Not established`

No public API price was substituted, provider cost was not recorded as zero, and no monetary break-even point was calculated.

## Unresolved parents and mechanisms not evaluated

The complete parent H-M1, H-V1, H-I1, H-O1, H-RCV1, and H-P1 hypotheses remain `Not established`. The supported sub-hypotheses do not silently establish them.

The following remain exactly `Not evaluated` in this closure batch:

- H-G1 — trace-informed proposals versus score-only random textual mutation;
- H-W1 — code-represented workflow search;
- H-C1 — confidence-based weak-to-strong cascade;
- H-R1 — task-feature strong/weak routing.

Fine-tuning, architecture search, routing, cascading, retry/recovery/escalation experiments beyond the already completed deterministic H-RCV1a scope, and all Phase 5 work were not performed.

## Invalid and superseded attempts

- Phase 3 `pilot-20260828-local` is preserved as invalid after its final manifest serialization failure; its aggregate is disqualified. The corrected rerun used a new identity.
- The original specialization fake `dry-run-20260901-local-01` is preserved unchanged with historical `Unknown` / `unavailable` vocabulary. It is superseded for future execution semantics by the corrected contract and `qualification-20260901-local-02`, not rewritten.
- `design-20260901-chatgpt-01` is preserved as `incomplete-blocked`: 24 Luna and 2 Terra formal attempts encountered deterministic provider schema compatibility errors; no eligible optimizer candidate, validation, blind inventory, or H-P1a result was formed.
- `design-20260901-chatgpt-02` is preserved as `incomplete-blocked-pre-invocation`: relative admission-path binding failed with zero formal model, network, and API calls.
- `design-20260902-chatgpt-03` plus `blind-20260902-chatgpt-03` is the valid replacement attempt. Prior attempts are excluded from its independent call ceiling and substantive aggregate.

No invalid attempt was overwritten, repaired in place, retried silently, or hidden by history rewriting.

## Provider and generalization uncertainty

The formal execution identity was OpenAI through Codex CLI, authenticated by the connected ChatGPT subscription path. Static schema preflight and the observed local catalog reduced deterministic admission errors but cannot make `gpt-5.6-luna` or `gpt-5.6-terra` aliases immutable. Provider implementation, alias behavior, catalog contents, and service-side schema validation may drift over time; no date-versioned immutable provider snapshot was available.

Difficulty calibration and real-workload representativeness remain `Unclear`. Generalization beyond the four generated families, `{"count": 4}` difficulty, 32 blind tasks, declared oracle, observed provider aliases, medium reasoning, no-tool envelope, and exact seed/C1 programs is `Not established`. Production, concurrent, multi-host, adversarial, shifted-distribution, days/weeks, crash/restart, network-failure, external-action, irreversible-action, compensation, maintenance, and deployment-threshold evidence is absent or outside scope.

## Closure decision

# Phase 4 complete — evidence sufficient to begin architecture synthesis

This decision closes the Phase 4 evidence program. It authorizes only a later, separately scoped and owner-authorized architecture-synthesis phase. No architecture is synthesized here, no architecture is implemented, and Phase 5 is not started.
