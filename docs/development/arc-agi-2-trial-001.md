# ARC-AGI-2 Trial 001 Development and Validation

Status: implemented repository path; real model/solver execution is not
authorized and no model or solver is selected, downloaded, or bound.

Decision 0004 is the product authority. The tracked
[`trial profile`](../../trials/first-real-domain/trial-profile.json) fixes the
official source, split boundary, pass@2 evaluator, single permitted
specialization difference, zero external budget, and five-percentage-point P2
acceptance gate.

## Networked source acquisition

This is the only command in the Trial 001 path allowed to use the network. It
has no repository argument: it can acquire only the official
`https://github.com/arcprize/ARC-AGI-2.git` repository at detached commit
`f3283f727488ad98fe575ea6a5ac981e4a188e49`.

```powershell
python -m irisx arc-agi-2 source materialize --output .irisx\arc-agi-2\trial-001\source
```

The command preserves the checkout bytes, verifies the exact Git remote and
commit, validates 1,000 training and 120 evaluation tasks, and records every
tracked file's byte count and SHA-256 digest in `provenance.json`. It rejects a
branch head, changed checkout, missing or extra task, wrong source, or stale
manifest.

## Offline preparation and validation

All remaining commands are offline:

```powershell
python -m irisx arc-agi-2 source validate .irisx\arc-agi-2\trial-001\source
python -m irisx arc-agi-2 trial prepare --source .irisx\arc-agi-2\trial-001\source --output .irisx\arc-agi-2\trial-001\trial
python -m irisx arc-agi-2 trial validate .irisx\arc-agi-2\trial-001\trial
python -m irisx arc-agi-2 trial preflight .irisx\arc-agi-2\trial-001\trial --output .irisx\arc-agi-2\trial-001\preflight\report.json
```

Preparation writes separate solver-facing and evaluator-only artifacts. The
solver artifact contains demonstrations and test inputs only. The evaluator
truth artifact contains expected test outputs and is never returned by the
solver payload API. Workload expected references bind truth for independent
evaluation, but neither the WorkloadDefinition nor those references are solver
inputs. Each logical locator begins with the retained artifact path and is
resolved back to the exact case value and digest during validation. The Domain
Specification similarly resolves its material reference to the retained source
provenance artifact. Specialization derivation receives only all 1,000
public-training files, records their exact source digests, computes shape and
palette observations, and deterministically renders its policy from those
observations.

The unbound preflight is expected to exit non-zero. It reports the missing
local solver descriptor and asset, hardware identity, exact envelope binding,
and later owner run authorization. Both configurations bind the same exact
envelope through `workflow_control`. It also fails on provider credentials,
network/provider enablement, non-zero external budget, model substitution,
asset corruption, or an envelope mismatch. It prints credential names only,
never values.

There is deliberately no real-run command in this implementation. Adding a
generic executable adapter would settle a runtime boundary before the owner has
selected and bound the local solver. After a later decision supplies that
binding and a separate run authorization, the owner must authorize the exact
run adapter and command; Decision 0004 and this implementation do not do so.
The current validator does not accept a trial-local authorization document:
the later authorization must first become tracked repository authority through
a subsequent owner decision and implementation update.

## Future result, selection, and package evidence

The following command surface is reserved for evidence produced by a later,
separately authorized local run:

```powershell
python -m irisx arc-agi-2 result validate <run-directory>
python -m irisx arc-agi-2 select <run-directory>
python -m irisx arc-agi-2 package build --run <run-directory> --output <package-directory>
python -m irisx arc-agi-2 package verify <package-directory>
```

Under Decision 0004 alone these commands fail closed because no later tracked
run authority or authorized runtime adapter exists. Locally manufactured
predictions, observations, preflight reports, or authorization JSON cannot
unlock result admission, selection, or package construction. A later owner
decision must name the exact run authority and runtime boundary before these
commands can accept evidence.

Result validation recomputes every task from evaluator-only truth and requires
exactly two valid grids for every test input. Generic P1 selection remains
unchanged. The separate `irisx/p2-acceptance` artifact accepts only an eligible
candidate with at least `0.05` absolute ARC task-accuracy improvement. For the
fixed 120-task workload this gate is evaluated exactly as at least six
additional passed tasks, avoiding binary floating-point boundary errors. A
smaller positive improvement remains valid evidence but is package-ineligible.

After that later authorization and runtime closure, P2 package verification is
intended to remain closed-world and recompute prediction scoring,
EvaluationResults, generic selection, P2 acceptance, preflight identity,
limitations, contract references, every JSON digest, and the opaque local
solver asset digest. The current repository cannot emit a deployable P2 Domain
Package. Any future eligible package must require these four limitations:

- evaluation covers only the pinned public ARC-AGI-2 evaluation snapshot;
- no claim is made about semi-private or private performance;
- no ARC Prize or state-of-the-art claim is made; and
- only the first minimal specialization intervention was tested.

## Official README discrepancy

The pinned official README's formal “Task success criterion” says two trials
per test input, and its evaluation-set description says controlled solvers used
two attempts or fewer. A later task-format paragraph says “3 trials,” while the
same README also says the browser interface does not enforce the two-trial
rule. Decision 0004 explicitly pins pass@2. The implementation therefore uses
exactly two predictions and records this isolated documentation inconsistency;
it does not reinterpret the admitted evaluator.
