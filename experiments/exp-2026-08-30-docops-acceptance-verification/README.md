# Experiment: Independent Acceptance Verification

- **Experiment ID:** `exp-2026-08-30-docops-acceptance-verification`
- **Status:** defined; local run executed and reviewed
- **Hypothesis:** `H-V1a`
- **Distribution:** `taskdist-2026-08-28-vanta-docops-readonly-12`
- **Task contract:** `research/task-contract-docops-readonly-12.md`
- **Source snapshot:** `src.vanta` / `snap.src.vanta.initial-import`
- **Corpus evidence:** `src.vanta` Evidence Packet/verifier separation and
  false-accept/false-reject tracking; imported architecture is not adopted

## Research Question

On frozen claimed-success outputs over the existing 12-task development
distribution, does an independent deterministic acceptance decision reduce
false-success acceptance relative to claim-only acceptance without rejecting
semantically valid outputs?

## Isolated Intervention

The only arm difference is acceptance policy:

- `claim-only-v0`: accept when `system_claim == success`.
- `independent-verify-v0`: accept only when `system_claim == success` and the
  independent verifier returns `accept`.

For every paired record the task, source bytes, source snapshot, exact producer
output string, system claim, complete evidence/path hashes, independently
adjudicated actual outcome, challenge case, order, repetition, and resource
envelope are fixed. The treatment never changes producer output.

`H-V1b — evidence/provenance binding: deferred / not evaluated in this batch`

## Frozen Challenge Set

`scripts/build_challenges.py` deterministically derives five outputs per task:

1. canonical valid;
2. semantic-equivalent valid with different ordering/formatting;
3. omission invalid;
4. fabrication invalid;
5. corruption/wrong-value invalid.

The builder proves the two valid variants parse equal to the declared fixture
oracle and the three invalid variants parse unequal. Shape-specific fallback
notes remain in challenge metadata. Mutation metadata is not included in the
verifier function signature or call.

The frozen horizon is 60 cases × two arms × three repetitions = 360 paired-arm
terminal records. Before execution the complete artifact is committed and its
SHA-256 is recorded in the run manifest.

Frozen challenge SHA-256:
`398342dee4aee9651e6c2350f8abdde34cff57cc2ae0e19f0110a33f7321d859`.

## Outcome and Verifier Separation

Actual outcome is independently adjudicated under the Phase 3 semantic JSON
and no-mutation contract. The verifier separately reloads the declared oracle
and parses the producer-output bytes; it is not passed the adjudicated outcome,
mutation type, expected semantic relation, or acceptance label. Verifier
acceptance is therefore a mechanism decision, not empirical truth by
definition.

## Measurements and Support Rule

Each arm reports true accept, true reject, false accept, false reject,
accepted/rejected claimed-success counts, verifier errors/invalids,
verification wall/CPU time, output/decision/terminal-record bytes, paired actual
outcome, and repeat agreement. No scalar score combines these outcomes.

H-V1a is supported task-locally only if treatment false accepts are lower,
canonical and semantic-equivalent valid outputs have no new rejection, paired
actual outcomes are identical, and no challenge labels enter the verifier
interface. A finite-sample zero false-accept count is not a claim of perfect or
general verifier reliability.

## Procedure

From repository root:

```powershell
python experiments\exp-2026-08-30-docops-acceptance-verification\scripts\build_challenges.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --output experiments\exp-2026-08-30-docops-acceptance-verification\inputs\challenges.json
python experiments\exp-2026-08-30-docops-acceptance-verification\scripts\build_challenges.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --output experiments\exp-2026-08-30-docops-acceptance-verification\inputs\challenges.json `
  --check
python experiments\exp-2026-08-30-docops-acceptance-verification\scripts\run_experiment.py `
  --challenges experiments\exp-2026-08-30-docops-acceptance-verification\inputs\challenges.json `
  --registry corpus\sources.yaml `
  --validate-only
python experiments\exp-2026-08-30-docops-acceptance-verification\scripts\run_experiment.py `
  --challenges experiments\exp-2026-08-30-docops-acceptance-verification\inputs\challenges.json `
  --registry corpus\sources.yaml `
  --output-dir experiments\exp-2026-08-30-docops-acceptance-verification\runs\<run-id> `
  --run-id <run-id>
```

Run directories are immutable. An invalid attempt is preserved with a failure
record and is not cited as a completed result.

Completed run:

- `runs/hv1a-20260830-local-01/`: 360/360 valid paired-arm records;
  reviewed `Supported — task-local` result. Treatment reduced false accepts
  from 108 to zero in the fixed sample without rejecting the 72 valid records.

## Boundaries

Local Python standard library only; no network, models, tokens/APIs,
credentials, paid services, retries, recovery, routing, optimization, imported
source write, or VANTA fixture mutation. Oracle validity beyond these declared
fixture bytes is `Not established`.
