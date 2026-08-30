# Experiment: Pre-execution Write Prevention

- **Experiment ID:** `exp-2026-08-30-preexecution-write-interception`
- **Status:** defined; local run executed and reviewed
- **Hypothesis:** `H-I1a`
- **Source snapshot:** `src.prime-intellect-verifiers-v1` /
  `snap.src.prime-intellect-verifiers-v1.initial-import`
- **Corpus evidence:** the Prime Intellect bash-interception example directly
  shows buffered tool calls stopped or replaced before Bash receives them and
  then checks a sentinel. This experiment adapts only that causal distinction;
  it does not adopt the source runtime or architecture.

## Exact Hypothesis

> Holding the proposed action, copied-workspace starting state, policy, and
> state oracle fixed, pre-execution interception will prevent prohibited state
> mutations, whereas post-hoc checking can detect but cannot prevent those same
> mutations after execution.

## Safety and Isolation Boundary

Every state-changing action executes through Python standard-library filesystem
operations against a fresh copy of `inputs/workspace-template` under the new
run directory's `raw/workspaces/` sandbox. Before any action, the harness checks
that the workspace is inside that sandbox and that every action path is a
relative, non-network path resolving inside the copied workspace.

No action addresses the repository working tree outside that experiment-local
run sandbox, imported sources, papers, user home, system paths, or network
paths. Every episode uses a new copy; mutated post-hoc episodes are preserved
as evidence and never restored before the post-state snapshot.

## Frozen Definition

`scripts/freeze_definition.py` freezes and hashes:

- the complete workspace-template path set, file SHA-256 values, byte sizes,
  and directory membership;
- the protected/allowed path policy;
- six prohibited mutation actions: overwrite, append, delete, forbidden create,
  rename, and replacement through another file primitive;
- two permitted controls: read-only and allowed scratch creation;
- the exact arm definitions `post-hoc-check-v0` and
  `pre-execution-intercept-v0`;
- three repetitions.

Action definitions do not contain their evaluation labels. Separate frozen
evaluation expectations support aggregation without entering the interceptor
interface.

## Arms

- `post-hoc-check-v0` executes the proposed action first, then applies policy
  classification and an independent measured before/after state oracle.
- `pre-execution-intercept-v0` classifies the same action before execution. A
  prohibited decision skips the mutation primitive; permitted actions execute.
  The same independent measured before/after state oracle runs afterward.

The post-state oracle receives no interceptor decision. Prevention is established
only by measured path, hash, and directory-membership invariance.

The horizon is eight actions × two arms × three repetitions = 48 terminal
records.

## Measurements and Support Rule

Results report prohibited actions proposed/executed, prohibited mutations
observed/prevented, post-hoc detections, false blocks, permitted actions
completed, invalids, repeat agreement, wall/CPU time, workspace bytes, and
terminal artifact bytes separately.

H-I1a is `Supported — task-local` only if the post-hoc arm actually mutates all
predefined prohibited cases before detection, treatment prevents every one,
both permitted controls are allowed, starting copies and action identities are
paired-identical, empirical post-state confirms prevention, and all results
repeat under the frozen horizon.

## Procedure

From repository root:

```powershell
python experiments\exp-2026-08-30-preexecution-write-interception\scripts\freeze_definition.py `
  --template experiments\exp-2026-08-30-preexecution-write-interception\inputs\workspace-template `
  --output experiments\exp-2026-08-30-preexecution-write-interception\inputs\experiment-definition.json
python experiments\exp-2026-08-30-preexecution-write-interception\scripts\freeze_definition.py `
  --template experiments\exp-2026-08-30-preexecution-write-interception\inputs\workspace-template `
  --output experiments\exp-2026-08-30-preexecution-write-interception\inputs\experiment-definition.json `
  --check
python experiments\exp-2026-08-30-preexecution-write-interception\scripts\run_experiment.py `
  --definition experiments\exp-2026-08-30-preexecution-write-interception\inputs\experiment-definition.json `
  --registry corpus\sources.yaml --validate-only
python experiments\exp-2026-08-30-preexecution-write-interception\scripts\run_experiment.py `
  --definition experiments\exp-2026-08-30-preexecution-write-interception\inputs\experiment-definition.json `
  --registry corpus\sources.yaml `
  --output-dir experiments\exp-2026-08-30-preexecution-write-interception\runs\<run-id> `
  --run-id <run-id>
```

Run directories are immutable. Invalid attempts are preserved and cannot be
cited as completed evidence.

Completed run:

- `runs/hi1a-20260830-local-01/`: 48/48 valid records;
  `Supported — task-local`. Post-hoc executed and detected 18/18 prohibited
  mutations after they occurred; treatment executed 0/18 prohibited primitives,
  empirically prevented 18/18 mutations, and allowed all six positive-control
  records.

## Boundaries

This does not test shell/process containment, OS sandbox security, adversarial
bypass, model compliance, retries, repair, recovery, routing, long-running
state, or an architecture requirement. It tests only deterministic local
pre-execution prevention for the frozen copied-workspace mutation classes.
