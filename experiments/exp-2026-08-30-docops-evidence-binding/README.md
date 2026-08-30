# Experiment: Evidence / Provenance Binding

- **Experiment ID:** `exp-2026-08-30-docops-evidence-binding`
- **Status:** defined; frozen challenge pending measured execution
- **Hypothesis:** `H-V1b`
- **Distribution:** `taskdist-2026-08-28-vanta-docops-readonly-12`
- **Task contract:** `research/task-contract-docops-readonly-12.md`
- **Source snapshot:** `src.vanta` / `snap.src.vanta.initial-import`
- **Corpus evidence:** VANTA Evidence Packet/verifier material motivates externally
  grounded evidence and separate verifier decisions; its architecture is not
  adopted.

## Exact Hypothesis

> Holding actual output, actual outcome, system claim, task bytes, semantic
> verifier behavior, and execution path fixed, evidence-bound verification will
> distinguish success supported by complete path/hash evidence from success
> accompanied by missing, stale, crossed, unrelated, conflicting, or otherwise
> invalid evidence, while leaving actual outcome unchanged.

## Isolated Intervention

Every main challenge producer output is the canonical semantically correct
fixture observation and every system claim is `success`. The only arm difference
is evidence eligibility:

- `semantic-only-v0` uses the fixed successful semantic-verifier decision and
  does not enforce the supplied evidence envelope.
- `evidence-bound-v0` independently resolves each supplied path inside the
  fixture, reads the actual bytes, recomputes SHA-256 and byte size, checks the
  declared-input identity and role, and rejects missing, extra, or conflicting
  entries.

Actual outcome is adjudicated independently and remains `success`; insufficient
or invalid evidence produces `unverified_success`, not task failure. The evidence
verifier receives only the fixture boundary, declared path/role requirements,
and supplied envelope. It receives no case ID, variant ID, expected validity,
actual outcome, or semantic-verifier result.

## Frozen Challenge Set

The deterministic builder creates eight evidence variants for each of 12 tasks:

1. `complete-correct`;
2. `missing-required-entry`;
3. `wrong-hash`;
4. `stale-hash`, using the authored `inputs/stale-evidence-bytes.txt` hash;
5. `crossed-evidence`;
6. `unrelated-existing-file`;
7. `conflicting-duplicate`;
8. `correct-hash-wrong-path`.

For multi-input tasks, `crossed-evidence` swaps the first two declared
path/hash/size associations while retaining the declared paths. For a
single-input task, the predeclared fallback replaces its entry with the next
task's first declared input, expressed relative to the current fixture; this
must fail the current fixture boundary/declared-input checks. The task order
wraps deterministically.

`unrelated-existing-file` retains all required entries and appends the existing
expected-observation file with its real recomputed hash. `correct-hash-wrong-path`
retains the correct hash of the intended input but associates it with
`task.json`. These rules are fixed before execution and cases are never silently
dropped.

The horizon is 96 cases × two arms × three repetitions = 576 terminal records.
The complete challenge artifact is committed and hashed before measured
execution.

## Measurements and Support Rule

Results report actual successes, verified-success eligibility,
unverified-success counts, false verified-success acceptance, false rejection
of complete evidence, reason categories, invalids, repeat agreement, evidence
verification wall/CPU time, evidence bytes, and terminal bytes separately.

H-V1b is `Supported — task-local` only if complete-correct evidence is accepted,
all seven predefined invalid/insufficient variants are denied eligibility,
actual outcome and semantic verification stay fixed across arms, no validity
label enters the verifier interface, and all decisions repeat under the declared
horizon.

## Procedure

From repository root:

```powershell
python experiments\exp-2026-08-30-docops-evidence-binding\scripts\build_challenges.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --stale-fixture experiments\exp-2026-08-30-docops-evidence-binding\inputs\stale-evidence-bytes.txt `
  --output experiments\exp-2026-08-30-docops-evidence-binding\inputs\challenges.json
python experiments\exp-2026-08-30-docops-evidence-binding\scripts\build_challenges.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --stale-fixture experiments\exp-2026-08-30-docops-evidence-binding\inputs\stale-evidence-bytes.txt `
  --output experiments\exp-2026-08-30-docops-evidence-binding\inputs\challenges.json `
  --check
python experiments\exp-2026-08-30-docops-evidence-binding\scripts\run_experiment.py `
  --challenges experiments\exp-2026-08-30-docops-evidence-binding\inputs\challenges.json `
  --registry corpus\sources.yaml --validate-only
python experiments\exp-2026-08-30-docops-evidence-binding\scripts\run_experiment.py `
  --challenges experiments\exp-2026-08-30-docops-evidence-binding\inputs\challenges.json `
  --registry corpus\sources.yaml `
  --output-dir experiments\exp-2026-08-30-docops-evidence-binding\runs\<run-id> `
  --run-id <run-id>
```

Run directories are immutable. Invalid attempts are preserved and cannot be
cited as completed evidence.

## Boundaries

Local Python standard library only; no network, models, tokens/APIs,
credentials, paid services, retries, recovery, routing, optimization, imported
source writes, or fixture mutation. A positive result is limited to this frozen
path/hash contract and does not establish causal provenance, universal evidence
sufficiency, parent H-V1, or architecture requirements.
