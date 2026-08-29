# Experiment: Structured Instrumentation Completeness

- **Experiment ID:** `exp-2026-08-30-docops-profile-instrumentation`
- **Status:** defined; profile contract frozen; not yet run
- **Hypothesis:** `H-O1a`
- **Distribution:** `taskdist-2026-08-28-vanta-docops-readonly-12`
- **Control behavior:** Phase 3 `structured-readonly-v0`
- **Task contract:** `research/task-contract-docops-readonly-12.md`
- **Corpus evidence:** `src.nemo-agent-toolkit-develop` per-invocation
  usage/timing and separate profiler artifacts; the toolkit is not a dependency

## Research Question

Can structured profiling capture a richer predeclared runtime profile while
leaving paired deterministic behavior unchanged, and what artifact/timing
overhead is observed?

## Isolated Intervention

- `instrumentation-off-v0` executes the Phase 3 structured control and retains
  only required terminal/cost fields.
- `instrumentation-on-v0` executes the same control and evaluator while adding
  one structured profile and five experiment-local stage events.

Neither arm adds retry, recovery, verifier gating, routing, caching changes,
optimization, model calls, or another runtime.

The runner loads the existing Phase 3 implementation directly rather than
refactoring it for code reuse. Task manifest, configuration, behavior,
evaluator, resource envelope, task order, and repetitions remain fixed.

## Frozen Profile Contract

`inputs/profile-contract.json` predeclares 17 task-relevant fields covering:

- profile/episode/task/arm identity;
- invocation and evaluation stage identity and timing;
- read count and bytes read;
- serialized producer-output bytes;
- terminal status;
- instrumentation event count;
- profiler error/failure state.

The required field set is frozen before the measured run. It excludes model,
token, cache, network, and forecasting fields that are meaningless for this
local deterministic control.

## Horizon and Measurements

The intended horizon is 12 tasks × two arms × three repetitions = 72 terminal
episodes. Measurements include declared field coverage/missingness, paired
output equality, paired actual-outcome and terminal-status equality,
invalid/harness failures, profile artifact bytes, producer/terminal bytes, and
available wall/CPU timings.

H-O1a is supported task-locally only if instrumentation improves coverage,
paired outputs/outcomes remain identical, terminal status remains identical,
and no new invalid episode is introduced. Timing and artifact size are
descriptive; no overhead threshold is invented.

## Procedure

From repository root:

```powershell
python -m py_compile experiments\exp-2026-08-30-docops-profile-instrumentation\scripts\run_experiment.py
python experiments\exp-2026-08-30-docops-profile-instrumentation\scripts\run_experiment.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --configurations experiments\exp-2026-08-28-docops-readonly-baseline\inputs\configurations.json `
  --profile-contract experiments\exp-2026-08-30-docops-profile-instrumentation\inputs\profile-contract.json `
  --registry corpus\sources.yaml `
  --validate-only
python experiments\exp-2026-08-30-docops-profile-instrumentation\scripts\run_experiment.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --configurations experiments\exp-2026-08-28-docops-readonly-baseline\inputs\configurations.json `
  --profile-contract experiments\exp-2026-08-30-docops-profile-instrumentation\inputs\profile-contract.json `
  --registry corpus\sources.yaml `
  --output-dir experiments\exp-2026-08-30-docops-profile-instrumentation\runs\<run-id> `
  --run-id <run-id>
```

Run directories are immutable. Invalid attempts are preserved and cannot be
cited as completed results.

## Boundaries

Local Python standard library only; no network, models, tokens/APIs,
credentials, paid services, imported-source write, or fixture mutation. These
short same-host runs cannot establish stable production performance overhead.
