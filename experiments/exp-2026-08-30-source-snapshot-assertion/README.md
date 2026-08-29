# Experiment: Registered Source Snapshot Assertion

- **Experiment ID:** `exp-2026-08-30-source-snapshot-assertion`
- **Status:** defined; local run executed and reviewed
- **Hypothesis:** `H-M1a`
- **Distribution:** `taskdist-2026-08-28-vanta-docops-readonly-12`
- **Registry:** `corpus/sources.yaml`
- **Corpus evidence:** `src.spex` run-manifest identity validation and
  terminal-record discipline; the mechanism remains IRIS-X experiment-local

## Research Question

Does resolving the registered source snapshot and enforcing exact source-tree
identity detect provenance mismatches that the Phase 3 record-only behavior
would not reject?

## Arms

- `record-only-v0` records the requested source ID, snapshot ID, and observed
  tree OID without resolving or enforcing the registry relation.
- `registry-assert-v0` parses the actual registry format, resolves the source
  and snapshot, validates the active/current relationship, obtains the source
  tree at the code commit, and fails closed on an unresolved or unequal
  identity.

The runner contains only the resolver/assertion needed for this experiment. It
is not a general provenance framework.

## Frozen Cases and Horizon

`inputs/challenges.json` declares one valid identity and four deterministic
mismatches: unknown source, unknown snapshot, synthetic observed-tree mismatch,
and a source/snapshot relationship mismatch. The synthetic observed OID does
not mutate imported source. Each arm executes every case three times, for 30
terminal records.

Expected mismatch labels are used only to score the completed decisions. They
are not passed to the registry resolver or equality assertion.

## Measurements and Support Rule

Raw records retain expected/detected/missed mismatch flags, false-positive
valid rejection, decision reason, validity, repeat identity, registry bytes,
Git lookups, terminal-record bytes, and local wall/CPU time. Aggregates report
identity-decision confusion counts separately by arm.

H-M1a is supported only if the treatment accepts the valid identity, rejects
all predefined mismatches, the control misses at least one treatment-detected
mismatch, and decisions agree across all three repetitions. This would be
task-local harness-integrity evidence only; it would not establish the complete
H-M1 parent.

## Procedure

From repository root:

```powershell
python -m py_compile experiments\exp-2026-08-30-source-snapshot-assertion\scripts\run_experiment.py
python experiments\exp-2026-08-30-source-snapshot-assertion\scripts\run_experiment.py `
  --challenges experiments\exp-2026-08-30-source-snapshot-assertion\inputs\challenges.json `
  --registry corpus\sources.yaml `
  --validate-only
python experiments\exp-2026-08-30-source-snapshot-assertion\scripts\run_experiment.py `
  --challenges experiments\exp-2026-08-30-source-snapshot-assertion\inputs\challenges.json `
  --registry corpus\sources.yaml `
  --output-dir experiments\exp-2026-08-30-source-snapshot-assertion\runs\<run-id> `
  --run-id <run-id>
```

Run directories are immutable. If a run becomes invalid after writing
artifacts, retain it with `failure.json` and rerun under a new ID.

Completed run:

- `runs/hm1a-20260830-local-01/`: 30/30 valid terminal records; reviewed
  `Supported — task-local` result. The interpretation records the exact
  task-local boundary and descriptive verification cost.

## Boundaries

Local Python standard library only; no network, model, token/API usage,
credentials, paid service, source mutation, or imported-source write. Upstream
source provenance remains `Unknown`; a matching registered Git tree establishes
only the declared local snapshot relation.
